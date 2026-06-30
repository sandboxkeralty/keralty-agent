from fastapi import APIRouter, HTTPException, Request
from typing import List, Dict, Any
from services.firestore import FirestoreService

router = APIRouter(prefix="/api/tasks", tags=["tasks"])

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
    
    # In a fully connected ADK flow, we'd signal the runner to resume here
    # e.g. runner.resume_task(task_id, "approved")
    
    return {"status": "success", "task_id": task_id, "result": "approved"}

@router.post("/{task_id}/reject")
async def reject_task(task_id: str, request: Request):
    user_id = getattr(request.state, "user", {}).get("uid", "sandbox-user")
    task = FirestoreService.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
        
    if task.get("user_id") != user_id:
        raise HTTPException(status_code=403, detail="Not authorized to reject this task")
        
    FirestoreService.update_task(task_id, {"status": "rejected"})
    
    # In a fully connected ADK flow, we'd signal the runner to resume here
    # e.g. runner.resume_task(task_id, "rejected")
    
    return {"status": "success", "task_id": task_id, "result": "rejected"}
