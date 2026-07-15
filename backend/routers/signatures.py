"""Per-executive signature management (see services/signature_service.py).

Mounted at /api/signatures so the standard auth middleware covers it. NOT
admin-gated on purpose: signatures are personal assets, same as writing
styles — the management UI happens to live in the admin panel, but the data
is always scoped to the authenticated user.
"""

import hashlib
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, File, HTTPException, Request, UploadFile
from pydantic import BaseModel, Field

from config import settings
from models.schemas import AuditEvent
from services import signature_service
from services.firestore import FirestoreService

router = APIRouter(prefix="/api/signatures", tags=["signatures"])

_EXT_TO_CONTENT_TYPE = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg"}


def _user_id(request: Request) -> str:
    user = getattr(request.state, "user", {}) or {}
    uid = user.get("email") or user.get("uid")
    if not uid:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return uid


def _audit(user_id: str, action: str, resource_id: str) -> None:
    try:
        FirestoreService.log_audit_event(AuditEvent(
            event_id=str(uuid.uuid4()),
            user_email_hash=hashlib.sha256(user_id.encode()).hexdigest(),
            action=action,
            resource_type="signature",
            resource_id=resource_id,
            timestamp=datetime.now(timezone.utc),
        ))
    except Exception:
        pass


class SignatureCreate(BaseModel):
    label: str = Field(min_length=1, max_length=signature_service.MAX_LABEL_CHARS)
    content: str = Field(min_length=1, max_length=signature_service.MAX_CONTENT_CHARS)
    logo_url: Optional[str] = None


class SignatureUpdate(BaseModel):
    label: Optional[str] = Field(default=None, max_length=signature_service.MAX_LABEL_CHARS)
    content: Optional[str] = Field(default=None, max_length=signature_service.MAX_CONTENT_CHARS)
    logo_url: Optional[str] = None


class ActiveSignature(BaseModel):
    signature_id: Optional[str] = None


@router.get("")
async def list_signatures(request: Request):
    user_id = _user_id(request)
    return {
        "signatures": signature_service.list_user_signatures(user_id),
        "active_signature_id": signature_service.get_active_signature_id(user_id),
    }


@router.post("", status_code=201)
async def create_signature(request: Request, body: SignatureCreate):
    user_id = _user_id(request)
    sig = signature_service.create_signature(user_id, body.label, body.content, body.logo_url)
    _audit(user_id, "signature_create", sig["signature_id"])
    return sig


@router.patch("/{signature_id}")
async def update_signature(signature_id: str, request: Request, body: SignatureUpdate):
    user_id = _user_id(request)
    updated = signature_service.update_signature(
        signature_id, user_id, body.model_dump(exclude_none=True)
    )
    if updated is None:
        raise HTTPException(status_code=404, detail="Signature not found.")
    _audit(user_id, "signature_update", signature_id)
    return updated


@router.delete("/{signature_id}")
async def delete_signature(signature_id: str, request: Request):
    user_id = _user_id(request)
    if not signature_service.delete_signature(signature_id, user_id):
        raise HTTPException(status_code=404, detail="Signature not found.")
    _audit(user_id, "signature_delete", signature_id)
    return {"deleted": True}


@router.put("/active")
async def set_active(request: Request, body: ActiveSignature):
    user_id = _user_id(request)
    if body.signature_id is not None:
        # Ownership check: never let a user point at someone else's signature.
        sigs = {s["signature_id"] for s in signature_service.list_user_signatures(user_id)}
        if body.signature_id not in sigs:
            raise HTTPException(status_code=404, detail="Signature not found.")
    signature_service.set_active_signature(user_id, body.signature_id)
    _audit(user_id, "signature_set_active", body.signature_id or "none")
    return {"active_signature_id": body.signature_id}


@router.post("/logo")
async def upload_logo(request: Request, file: UploadFile = File(...)):
    """Uploads a signature logo to GCS and returns its public URL.

    A public URL is required by both consumers: Gmail renders remote <img>
    sources, and the Docs API's insertInlineImage only accepts publicly
    accessible URIs. make_public() works because the bucket has uniform
    bucket-level access disabled (see the Imagen notes in CLAUDE.md).
    """
    user_id = _user_id(request)
    ext = (file.filename or "").rsplit(".", 1)[-1].lower() if "." in (file.filename or "") else ""
    if ext not in signature_service.ALLOWED_LOGO_EXTENSIONS:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported logo type '.{ext}'. Allowed: "
                   f"{', '.join(sorted(signature_service.ALLOWED_LOGO_EXTENSIONS))}",
        )
    data = await file.read()
    if len(data) > signature_service.MAX_LOGO_BYTES:
        raise HTTPException(status_code=413, detail="Logo exceeds 2 MB limit.")

    from google.cloud import storage
    client = storage.Client(project=settings.GOOGLE_CLOUD_PROJECT)
    bucket = client.bucket(settings.GCS_BUCKET)
    blob = bucket.blob(f"signatures/{uuid.uuid4()}.{ext}")
    blob.upload_from_string(data, content_type=_EXT_TO_CONTENT_TYPE[ext])
    blob.make_public()
    _audit(user_id, "signature_logo_upload", blob.name)
    return {"logo_url": blob.public_url}
