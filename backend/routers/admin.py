from fastapi import APIRouter, HTTPException, Depends
from typing import List, Dict
from config import settings

router = APIRouter(prefix="/admin", tags=["admin"])

def check_admin_enabled():
    if not settings.ADMIN_PANEL_ENABLED:
        raise HTTPException(status_code=403, detail="Admin panel is disabled.")

@router.get("/users", dependencies=[Depends(check_admin_enabled)])
def list_users():
    return {"users": []}

@router.post("/users", dependencies=[Depends(check_admin_enabled)])
def create_user(user_data: dict):
    return {"status": "created", "user": user_data}

@router.patch("/users/{email}", dependencies=[Depends(check_admin_enabled)])
def update_user(email: str, user_data: dict):
    return {"status": "updated", "email": email}

@router.get("/configs", dependencies=[Depends(check_admin_enabled)])
def list_configs():
    return {"configs": []}

@router.patch("/configs/{name}", dependencies=[Depends(check_admin_enabled)])
def update_config(name: str, config_data: dict):
    return {"status": "updated", "config": name}

@router.get("/metrics", dependencies=[Depends(check_admin_enabled)])
def get_metrics():
    return {"metrics": {"tokens": 0, "sessions": 0, "costs": 0}}

@router.get("/audit", dependencies=[Depends(check_admin_enabled)])
def get_audit_logs():
    return {"logs": []}
