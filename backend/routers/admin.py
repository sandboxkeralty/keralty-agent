from fastapi import APIRouter, Depends, HTTPException, Request
from typing import List, Dict, Any

from config import settings
from services.firestore import FirestoreService

router = APIRouter(prefix="/admin", tags=["admin"])


def _check_enabled():
    if not settings.ADMIN_PANEL_ENABLED:
        raise HTTPException(status_code=403, detail="Admin panel is disabled.")


# ── Users ──────────────────────────────────────────────────────────────────────

@router.get("/users", dependencies=[Depends(_check_enabled)])
def list_users(limit: int = 100) -> Dict[str, Any]:
    users = FirestoreService.list_users(limit=limit)
    return {"users": users, "count": len(users)}


@router.patch("/users/{email}", dependencies=[Depends(_check_enabled)])
def update_user(email: str, user_data: dict, request: Request) -> Dict[str, Any]:
    from google.cloud import firestore as _fs
    allowed_fields = {"name", "role"}
    updates = {k: v for k, v in user_data.items() if k in allowed_fields}
    if not updates:
        raise HTTPException(status_code=400, detail="No valid fields to update.")
    from services.firestore import db
    db.collection("users").document(email).update(updates)
    return {"status": "updated", "email": email, "updates": updates}


# ── Metrics ────────────────────────────────────────────────────────────────────

@router.get("/metrics", dependencies=[Depends(_check_enabled)])
def get_metrics() -> Dict[str, Any]:
    metrics = FirestoreService.get_metrics()
    return {"metrics": metrics}


# ── Audit log ──────────────────────────────────────────────────────────────────

@router.get("/audit", dependencies=[Depends(_check_enabled)])
def get_audit_logs(limit: int = 50) -> Dict[str, Any]:
    logs = FirestoreService.get_audit_logs(limit=limit)
    return {"logs": logs, "count": len(logs)}


# ── Config (feature flags read-only) ──────────────────────────────────────────

@router.get("/configs", dependencies=[Depends(_check_enabled)])
def list_configs() -> Dict[str, Any]:
    flag_fields = [
        "USE_VERTEX_AI", "USE_RAG_ENGINE", "USE_AGENT_ENGINE", "USE_LIVEKIT",
        "SEARCH_GROUNDING_ENABLED", "VOICE_ENABLED", "SLIDES_ENABLED",
        "IMAGE_GEN_ENABLED", "ADMIN_PANEL_ENABLED", "KB_AGENT_ENABLED",
        "EMAIL_GMAIL_ENABLED", "EMAIL_SEND_ENABLED", "EMAIL_TRACKING_ENABLED",
        "OTEL_ENABLED", "ENVIRONMENT",
    ]
    configs = {f: getattr(settings, f) for f in flag_fields}
    return {"configs": configs}
