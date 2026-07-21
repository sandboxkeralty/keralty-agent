import hashlib
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel

from agents.runner import runner
from models.schemas import AuditEvent
from services import folder_service
from services.firestore import FirestoreService

router = APIRouter(prefix="/history", tags=["history"])


def _user_id(request: Request) -> str:
    user = getattr(request.state, "user", {}) or {}
    return user.get("email") or user.get("uid") or "sandbox-user"


async def _purge(user_id: str, session_id: str) -> None:
    """Real purge: session doc + messages + ADK memory (adk_sessions doc and
    its events subcollection). audit_events are deliberately never touched."""
    FirestoreService.purge_session_data(session_id)
    await runner.session_service.delete_session(
        app_name="agents", user_id=user_id, session_id=session_id
    )


@router.get("/")
def get_user_history(request: Request):
    user_id = _user_id(request)
    sessions = FirestoreService.get_sessions_by_user(user_id)
    result = []
    for s in sessions:
        messages = FirestoreService.get_messages(s.session_id)
        first_msg = messages[0].content[:120] if messages else ""
        result.append({
            "session_id": s.session_id,
            "title": s.title,
            "folder_id": s.folder_id,
            "created_at": s.created_at.isoformat(),
            "updated_at": s.updated_at.isoformat(),
            "message_count": len(messages),
            "preview": first_msg,
        })
    return {"sessions": result}


@router.delete("/")
async def delete_all_sessions(request: Request, folder_id: Optional[str] = Query(None)):
    """Bulk purge of all the user's conversations (or one folder's)."""
    user_id = _user_id(request)
    if folder_id:
        if folder_service.get_folder(folder_id, user_id) is None:
            raise HTTPException(status_code=404, detail="Folder not found")
        session_ids = folder_service.sessions_in_folder(user_id, folder_id)
    else:
        session_ids = [s.session_id for s in FirestoreService.get_sessions_by_user(user_id)]

    for sid in session_ids:
        await _purge(user_id, sid)

    try:
        FirestoreService.log_audit_event(AuditEvent(
            event_id=str(uuid.uuid4()),
            user_email_hash=hashlib.sha256(user_id.encode()).hexdigest(),
            action="chats_bulk_delete",
            resource_type="session",
            resource_id=folder_id or "all",
            timestamp=datetime.now(timezone.utc),
            metadata={"deleted": len(session_ids)},
        ))
    except Exception:
        pass
    return {"deleted": len(session_ids)}


class SessionFolder(BaseModel):
    folder_id: Optional[str] = None


@router.patch("/{session_id}/folder")
async def move_session(session_id: str, request: Request, body: SessionFolder):
    user_id = _user_id(request)
    session = FirestoreService.get_session(session_id)
    if not session or session.user_id != user_id:
        raise HTTPException(status_code=404, detail="Session not found")
    if body.folder_id is not None and folder_service.get_folder(body.folder_id, user_id) is None:
        raise HTTPException(status_code=404, detail="Folder not found")
    FirestoreService.set_session_folder(session_id, body.folder_id)
    return {"session_id": session_id, "folder_id": body.folder_id}


class SessionTitle(BaseModel):
    title: str


@router.patch("/{session_id}/title")
async def rename_session(session_id: str, request: Request, body: SessionTitle):
    user_id = _user_id(request)
    session = FirestoreService.get_session(session_id)
    if not session or session.user_id != user_id:
        raise HTTPException(status_code=404, detail="Session not found")
    title = body.title.strip()[:100]
    if not title:
        raise HTTPException(status_code=422, detail="Title cannot be empty")
    FirestoreService.set_session_title(session_id, title)
    return {"session_id": session_id, "title": title}


@router.get("/{session_id}")
def get_session(session_id: str, request: Request):
    user_id = _user_id(request)
    session = FirestoreService.get_session(session_id)
    if not session or session.user_id != user_id:
        raise HTTPException(status_code=404, detail="Session not found")
    messages = FirestoreService.get_messages(session_id)
    return {
        "session": {
            "session_id": session.session_id,
            "title": session.title,
            "folder_id": session.folder_id,
            "created_at": session.created_at.isoformat(),
            "updated_at": session.updated_at.isoformat(),
        },
        "messages": [
            {
                "role": m.role,
                "content": m.content,
                "timestamp": m.timestamp.isoformat(),
            }
            for m in messages
        ],
    }


@router.delete("/{session_id}")
async def delete_session(session_id: str, request: Request):
    user_id = _user_id(request)
    session = FirestoreService.get_session(session_id)
    if not session or session.user_id != user_id:
        raise HTTPException(status_code=404, detail="Session not found")
    await _purge(user_id, session_id)
    return {"status": "deleted"}
