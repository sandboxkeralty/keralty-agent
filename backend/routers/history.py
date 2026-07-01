from fastapi import APIRouter, HTTPException, Request
from services.firestore import FirestoreService

router = APIRouter(prefix="/history", tags=["history"])

@router.get("/")
def get_user_history(request: Request):
    user = getattr(request.state, "user", {})
    user_id = user.get("email") or user.get("uid") or "sandbox-user"
    sessions = FirestoreService.get_sessions_by_user(user_id)
    result = []
    for s in sessions:
        messages = FirestoreService.get_messages(s.session_id)
        first_msg = messages[0].content[:120] if messages else ""
        result.append({
            "session_id": s.session_id,
            "title": s.title,
            "created_at": s.created_at.isoformat(),
            "updated_at": s.updated_at.isoformat(),
            "message_count": len(messages),
            "preview": first_msg,
        })
    return {"sessions": result}

@router.get("/{session_id}")
def get_session(session_id: str, request: Request):
    user = getattr(request.state, "user", {})
    user_id = user.get("email") or user.get("uid") or "sandbox-user"
    session = FirestoreService.get_session(session_id)
    if not session or session.user_id != user_id:
        raise HTTPException(status_code=404, detail="Session not found")
    messages = FirestoreService.get_messages(session_id)
    return {
        "session": {
            "session_id": session.session_id,
            "title": session.title,
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
def delete_session(session_id: str, request: Request):
    user = getattr(request.state, "user", {})
    user_id = user.get("email") or user.get("uid") or "sandbox-user"
    session = FirestoreService.get_session(session_id)
    if not session or session.user_id != user_id:
        raise HTTPException(status_code=404, detail="Session not found")
    # Delete session doc; messages are left for audit trail
    from google.cloud import firestore
    from config import settings
    db = firestore.Client(project=settings.GOOGLE_CLOUD_PROJECT, database=settings.FIRESTORE_DATABASE)
    db.collection("sessions").document(session_id).delete()
    return {"status": "deleted"}
