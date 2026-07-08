import hashlib
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Request
from typing import List, Dict, Any
from services.firestore import FirestoreService
from models.schemas import AuditEvent

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


def _log_hitl_event(action: str, user_id: str, task_id: str) -> None:
    FirestoreService.log_audit_event(AuditEvent(
        event_id=str(uuid.uuid4()),
        user_email_hash=hashlib.sha256(user_id.encode()).hexdigest(),
        action=action,
        resource_type="task",
        resource_id=task_id,
        timestamp=datetime.now(timezone.utc),
    ))

def _user_id(request: Request) -> str:
    # Auth middleware guarantees request.state.user on all /api/ paths (or 401s).
    # sub == email in every minted token (routers/auth.py), so this matches the
    # user_id that approval_tools/chat.py key tasks by.
    user = getattr(request.state, "user", {})
    return user.get("email") or user["uid"]


@router.get("", response_model=List[Dict[str, Any]])
async def get_tasks(request: Request):
    tasks = FirestoreService.get_pending_tasks(user_id=_user_id(request))
    return tasks

@router.post("/{task_id}/approve")
async def approve_task(task_id: str, request: Request):
    user_id = _user_id(request)
    task = FirestoreService.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if task.get("user_id") != user_id:
        raise HTTPException(status_code=403, detail="Not authorized to approve this task")

    if task.get("status") == "rejected":
        raise HTTPException(status_code=409, detail="Task was already rejected")

    FirestoreService.update_task(task_id, {"status": "approved"})
    _log_hitl_event("hitl_approved", user_id, task_id)

    task["status"] = "approved"
    return {"status": "success", "task_id": task_id, "task": task}

@router.post("/{task_id}/reject")
async def reject_task(task_id: str, request: Request):
    user_id = _user_id(request)
    task = FirestoreService.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
        
    if task.get("user_id") != user_id:
        raise HTTPException(status_code=403, detail="Not authorized to reject this task")
        
    FirestoreService.update_task(task_id, {"status": "rejected"})
    _log_hitl_event("hitl_rejected", user_id, task_id)

    return {"status": "success", "task_id": task_id, "result": "rejected"}
