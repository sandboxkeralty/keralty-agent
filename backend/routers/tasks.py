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

@router.get("", response_model=List[Dict[str, Any]])
async def get_tasks(request: Request):
    user_id = getattr(request.state, "user", {}).get("uid", "sandbox-user")
    tasks = FirestoreService.get_pending_tasks(user_id=user_id)
    return tasks

@router.post("/{task_id}/approve")
async def approve_task(task_id: str, request: Request):
    user_id = getattr(request.state, "user", {}).get("uid", "sandbox-user")
    task = FirestoreService.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
        
    if task.get("user_id") != user_id:
        raise HTTPException(status_code=403, detail="Not authorized to approve this task")
        
    FirestoreService.update_task(task_id, {"status": "approved"})
    _log_hitl_event("hitl_approved", user_id, task_id)

    task["status"] = "approved"
    return {"status": "success", "task_id": task_id, "task": task}

@router.post("/{task_id}/reject")
async def reject_task(task_id: str, request: Request):
    user_id = getattr(request.state, "user", {}).get("uid", "sandbox-user")
    task = FirestoreService.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
        
    if task.get("user_id") != user_id:
        raise HTTPException(status_code=403, detail="Not authorized to reject this task")
        
    FirestoreService.update_task(task_id, {"status": "rejected"})
    _log_hitl_event("hitl_rejected", user_id, task_id)

    return {"status": "success", "task_id": task_id, "result": "rejected"}
