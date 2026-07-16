"""Correo Ejecutivo v2 REST API.

Same /api/email prefix as routers/email.py (auto-covered by the auth
middleware's /api/ check). The legacy GET /summary endpoint stays in email.py
until the new frontend is deployed everywhere, then gets retired.

Scan progress streams over SSE with the exact frame format ChatWindow already
parses (data:{"type":...}\n\n) — no scan-status collection, no polling.
"""

import hashlib
import json
import queue
import threading
import uuid
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from routers.email import _credentials_for_user
from services.email import reply_service, scan_service, thread_store
from services.email.gmail_provider import GmailProvider
from services.firestore import FirestoreService

router = APIRouter(prefix="/api/email", tags=["email-v2"])

_VALID_STATES = {"gestionado", "resuelto"}
_VALID_PRIORITIES = {"CRITICO", "ALTO", "MEDIO", "BAJO"}
_VALID_ACTIONS = {"aceptar", "declinar", "mas_info", "delegar", "libre"}


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


# ---------------------------------------------------------------------------
# Phase 2 — search + dashboard draft cycle


@router.get("/search")
def search(request: Request, q: str, max: int = 25):
    """Gmail search joined with stored thread state — an analyzed hit shows its
    facets; an unanalyzed one is shown raw (search never triggers analysis)."""
    user_id = _user_id(request)
    creds = _credentials_for_user(user_id)
    max_results = min(max, 25)
    try:
        raw = GmailProvider.search_threads(q, max_results=max_results, credentials=creds)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Search failed: {e}")
    results, seen = [], set()
    for m in raw:
        tid = m.get("thread_id")
        if tid in seen:
            continue
        seen.add(tid)
        state = thread_store.get_thread(user_id, tid) if tid else None
        results.append({**m, "state": state})
    return {"status": "success", "results": results}


class DraftRequest(BaseModel):
    action: str
    instruction: str = ""
    language: Optional[str] = None  # es|en|None (None = match the sender)
    modifiers: List[str] = []       # shorter | more_formal
    previous_draft_id: Optional[str] = None


class DraftUpdate(BaseModel):
    to: str
    subject: str
    body: str
    thread_id: Optional[str] = None
    in_reply_to: Optional[str] = None
    references: Optional[str] = None


class ApprovalRequest(BaseModel):
    subject: str = ""
    to: str = ""
    preview: str = ""


@router.post("/threads/{thread_id}/draft")
def create_reply_draft(thread_id: str, body: DraftRequest, request: Request):
    if body.action not in _VALID_ACTIONS:
        raise HTTPException(status_code=422, detail="Invalid action")
    if body.language is not None and body.language not in ("es", "en"):
        raise HTTPException(status_code=422, detail="language must be es|en")
    user_id = _user_id(request)
    creds = _credentials_for_user(user_id)
    doc = thread_store.get_thread(user_id, thread_id)
    try:
        result = reply_service.generate_reply_draft(
            user_id=user_id, thread_id=thread_id, action=body.action,
            instruction=body.instruction, language=body.language,
            modifiers=body.modifiers, previous_draft_id=body.previous_draft_id,
            resumen=(doc or {}).get("resumen", ""), credentials=creds,
        )
        return {"status": "success", **result}
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Draft generation failed: {e}")


@router.put("/drafts/{draft_id}")
def update_draft(draft_id: str, body: DraftUpdate, request: Request):
    """Persists the executive's edits to the REAL Gmail draft — the edited text
    is what a later send actually delivers. The signature is re-applied
    server-side, so the edited body must stay signature-free."""
    user_id = _user_id(request)
    creds = _credentials_for_user(user_id)
    signature = None
    try:
        from services.signature_service import resolve_active
        signature = resolve_active(user_id)
    except Exception as e:
        print(f"[email_v2] signature lookup failed: {e}")
    try:
        new_id = GmailProvider.update_draft(
            draft_id, to=body.to, subject=body.subject, body=body.body,
            thread_id=body.thread_id, credentials=creds, signature=signature,
            in_reply_to=body.in_reply_to, references=body.references,
        )
        return {"status": "success", "draft_id": new_id}
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Draft update failed: {e}")


@router.delete("/drafts/{draft_id}")
def discard_draft(draft_id: str, request: Request):
    creds = _credentials_for_user(_user_id(request))
    try:
        GmailProvider.delete_draft(draft_id, credentials=creds)
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Draft delete failed: {e}")


@router.post("/drafts/{draft_id}/request-approval")
def request_approval(draft_id: str, body: ApprovalRequest, request: Request):
    """Creates the same approval task shape the chat flow uses
    (tools/approval_tools.py) — the send endpoint below verifies and consumes
    it server-side, identically to tools/_approval.py."""
    user_id = _user_id(request)
    task_id = str(uuid.uuid4())
    FirestoreService.create_task(task_id, {
        "type": "generic_approval",
        "description": f"Enviar correo (dashboard): {body.subject or draft_id}",
        "document_id": draft_id,
        "changes_summary": f"Para: {body.to}\n\n{body.preview[:1500]}",
        "status": "pending",
        "user_id": user_id,
    })
    return {"status": "pending_approval", "task_id": task_id}


@router.post("/drafts/{draft_id}/send")
def send_draft(draft_id: str, request: Request, thread_id: Optional[str] = None):
    """HITL-gated send: requires an approved, user-owned, not-yet-consumed task
    for this exact draft_id. One approval = one send."""
    user_id = _user_id(request)
    task = FirestoreService.find_approved_task(user_id, draft_id)
    if not task:
        raise HTTPException(
            status_code=403,
            detail="No hay una aprobación válida registrada para este borrador.")
    FirestoreService.consume_task(task["task_id"])

    creds = _credentials_for_user(user_id)
    try:
        message_id = GmailProvider.send_draft(draft_id, credentials=creds)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Send failed: {e}")

    try:
        from models.schemas import AuditEvent
        FirestoreService.log_audit_event(AuditEvent(
            event_id=str(uuid.uuid4()),
            user_email_hash=hashlib.sha256(user_id.encode()).hexdigest(),
            action="email_send",
            resource_type="email",
            resource_id=draft_id,
            timestamp=datetime.now(timezone.utc),
            metadata={"source": "dashboard"},
        ))
    except Exception as e:
        print(f"[email_v2] audit log failed: {e}")

    # Immediate UI state: replying marks the thread managed; a follow-up send
    # restarts its tracking clock. The next scan re-derives all of this from
    # Gmail authoritatively.
    if thread_id:
        doc = thread_store.update_thread(user_id, thread_id, {
            "estado_gestion": "gestionado",
            "esperando_respuesta": False,
        })
        if doc and doc.get("tracking_id"):
            followup_days = thread_store.get_email_settings(user_id)["followup_days"]
            try:
                thread_store.update_tracking(doc["tracking_id"], {
                    "status": "waiting",
                    "deadline": datetime.now(timezone.utc) + timedelta(days=followup_days),
                })
            except Exception as e:
                print(f"[email_v2] tracking reset failed: {e}")

    return {"status": "success", "sent": True, "message_id": message_id}
