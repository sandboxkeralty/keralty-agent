"""Correo Ejecutivo v2 REST API.

Same /api/email prefix as routers/email.py (auto-covered by the auth
middleware's /api/ check). The legacy GET /summary endpoint stays in email.py
until the new frontend is deployed everywhere, then gets retired.

Scan progress streams over SSE with the exact frame format ChatWindow already
parses (data:{"type":...}\n\n) — no scan-status collection, no polling.
"""

import json
import queue
import threading
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from routers.email import _credentials_for_user
from services.email import scan_service, thread_store

router = APIRouter(prefix="/api/email", tags=["email-v2"])

_VALID_STATES = {"gestionado", "resuelto"}
_VALID_PRIORITIES = {"CRITICO", "ALTO", "MEDIO", "BAJO"}


def _user_id(request: Request) -> str:
    user = getattr(request.state, "user", {}) or {}
    user_id = user.get("email") or user.get("uid")
    if not user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user_id


class StateUpdate(BaseModel):
    estado_gestion: str


class PriorityUpdate(BaseModel):
    prioridad: str


class PostponeRequest(BaseModel):
    until: str  # YYYY-MM-DD


class SettingsUpdate(BaseModel):
    window_days: Optional[int] = None
    followup_days: Optional[int] = None
    digest_email_enabled: Optional[bool] = None
    locale: Optional[str] = None


@router.post("/scan")
def scan(request: Request, tz: Optional[str] = None):
    """Incremental scan, streamed as SSE progress frames + a final done frame.

    run_scan is synchronous (Gmail + Gemini calls), so it runs in a worker
    thread pushing events into a queue the generator drains — progress frames
    reach the client while the scan is still working, and double as SSE
    keep-alives on Cloud Run.
    """
    user_id = _user_id(request)
    creds = _credentials_for_user(user_id)

    def event_stream():
        q: "queue.Queue[Optional[dict]]" = queue.Queue()

        def worker():
            try:
                result = scan_service.run_scan(user_id, creds, progress=q.put)
                q.put({"type": "done", **result})
            except Exception as e:
                print(f"[email_v2] scan failed: {e}")
                q.put({"type": "error", "detail": str(e)})
            finally:
                q.put(None)

        threading.Thread(target=worker, daemon=True).start()
        while True:
            evt = q.get()
            if evt is None:
                break
            yield f"data: {json.dumps(evt, default=str)}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.get("/threads")
def get_threads(request: Request):
    """Stored state only — instant first paint, no Gmail/Gemini calls."""
    user_id = _user_id(request)
    user_settings = thread_store.get_email_settings(user_id)
    return scan_service.assemble(user_id, user_settings)


@router.patch("/threads/{thread_id}/state")
def set_state(thread_id: str, body: StateUpdate, request: Request):
    if body.estado_gestion not in _VALID_STATES:
        raise HTTPException(status_code=422, detail="estado_gestion must be gestionado|resuelto")
    updates = {"estado_gestion": body.estado_gestion, "postponed_until": None}
    if body.estado_gestion == "resuelto":
        # "Ya no requiere seguimiento" — resolving removes it from Follow-up.
        updates["esperando_respuesta"] = False
    doc = thread_store.update_thread(_user_id(request), thread_id, updates)
    if doc is None:
        raise HTTPException(status_code=404, detail="Thread not found")
    return {"status": "success", "thread": doc}


@router.patch("/threads/{thread_id}/priority")
def set_priority(thread_id: str, body: PriorityUpdate, request: Request):
    if body.prioridad not in _VALID_PRIORITIES:
        raise HTTPException(status_code=422, detail="Invalid priority")
    doc = thread_store.update_thread(_user_id(request), thread_id, {
        "prioridad": body.prioridad,
        "prioridad_source": "user",
        "user_priority": body.prioridad,  # the floor: AI may raise, never lower
        "ai_reescalated": False,
    })
    if doc is None:
        raise HTTPException(status_code=404, detail="Thread not found")
    return {"status": "success", "thread": doc}


@router.post("/threads/{thread_id}/postpone")
def postpone(thread_id: str, body: PostponeRequest, request: Request):
    try:
        until = datetime.strptime(body.until, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except ValueError:
        raise HTTPException(status_code=422, detail="until must be YYYY-MM-DD")
    until_ms = int(until.timestamp() * 1000)
    if until_ms <= int(datetime.now(timezone.utc).timestamp() * 1000):
        raise HTTPException(status_code=422, detail="until must be a future date")
    doc = thread_store.update_thread(_user_id(request), thread_id, {
        "estado_gestion": "pospuesto",
        "postponed_until": until_ms,
        "esperando_respuesta": False,
    })
    if doc is None:
        raise HTTPException(status_code=404, detail="Thread not found")
    return {"status": "success", "thread": doc}


@router.get("/settings")
def get_settings_endpoint(request: Request):
    return {"status": "success", "settings": thread_store.get_email_settings(_user_id(request))}


@router.put("/settings")
def put_settings(body: SettingsUpdate, request: Request):
    saved = thread_store.update_email_settings(
        _user_id(request), body.model_dump(exclude_none=True))
    return {"status": "success", "settings": saved}
