"""Writing-style profile management (per-executive personalization).

Mounted at /api/style so the standard auth middleware covers it. Presets are
read-only code constants; custom styles live in Firestore `writing_styles`,
always ownership-checked against the authenticated user. Nothing here is
admin-gated on purpose: styles are personal assets managed by each executive.
"""

import hashlib
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, File, HTTPException, Request, UploadFile
from pydantic import BaseModel, Field

from models.schemas import AuditEvent
from services import style_service
from services.firestore import FirestoreService
from services.rag.ingestion import extract_text
from services.style_presets import PRESETS

router = APIRouter(prefix="/api/style", tags=["style"])

_ALLOWED_UPLOAD_TYPES = {"pdf", "docx", "doc", "txt", "csv", "md"}
_MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # per sample file


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
            resource_type="writing_style",
            resource_id=resource_id,
            timestamp=datetime.now(timezone.utc),
        ))
    except Exception:
        pass


class StyleCreate(BaseModel):
    name: str = Field(min_length=1, max_length=style_service.MAX_NAME_CHARS)
    description: Optional[str] = Field(default="", max_length=style_service.MAX_DESC_CHARS)
    style_guide: str = Field(min_length=1, max_length=style_service.MAX_GUIDE_CHARS)
    sample_filenames: Optional[List[str]] = None


class StyleUpdate(BaseModel):
    name: Optional[str] = Field(default=None, max_length=style_service.MAX_NAME_CHARS)
    description: Optional[str] = Field(default=None, max_length=style_service.MAX_DESC_CHARS)
    style_guide: Optional[str] = Field(default=None, max_length=style_service.MAX_GUIDE_CHARS)


class DefaultStyle(BaseModel):
    style_id: Optional[str] = None


@router.get("")
async def list_styles(request: Request):
    user_id = _user_id(request)
    return {
        "presets": PRESETS,
        "styles": style_service.list_user_styles(user_id),
        "default_style_id": style_service.get_default_style_id(user_id),
    }


@router.post("/analyze")
async def analyze_samples(request: Request, files: List[UploadFile] = File(...)):
    _user_id(request)  # auth check only; nothing is persisted here
    if not files:
        raise HTTPException(status_code=400, detail="Provide at least one sample file.")
    if len(files) > style_service.MAX_ANALYZE_FILES:
        raise HTTPException(
            status_code=400,
            detail=f"Maximum {style_service.MAX_ANALYZE_FILES} sample files per analysis.",
        )

    texts: List[str] = []
    filenames: List[str] = []
    truncated = False
    for f in files:
        ext = (f.filename or "").rsplit(".", 1)[-1].lower() if "." in (f.filename or "") else "txt"
        if ext not in _ALLOWED_UPLOAD_TYPES:
            raise HTTPException(status_code=415, detail=f"Unsupported file type: .{ext}")
        data = await f.read()
        if len(data) > _MAX_UPLOAD_BYTES:
            raise HTTPException(status_code=413, detail=f"File too large: {f.filename} (limit 10 MB)")
        try:
            text = extract_text(data, ext)
        except Exception:
            text = ""
        if text and text.strip():
            if len(text) > style_service.MAX_CHARS_PER_SAMPLE:
                truncated = True
            texts.append(text)
            filenames.append(f.filename or "sample")

    if not texts:
        raise HTTPException(status_code=422, detail="No readable text found in the uploaded files.")

    try:
        guide = style_service.analyze_samples(texts)
    except style_service.StyleAnalysisError:
        raise HTTPException(status_code=502, detail="Style analysis failed; try again.")
    except Exception as e:
        print(f"[style] analyze failed: {type(e).__name__}: {e}", flush=True)
        raise HTTPException(status_code=502, detail="Style analysis failed; try again.")

    return {"style_guide": guide, "sample_filenames": filenames, "truncated": truncated}


@router.post("", status_code=201)
async def create_style(request: Request, body: StyleCreate):
    user_id = _user_id(request)
    style = style_service.create_style(
        user_id, body.name, body.description or "", body.style_guide, body.sample_filenames
    )
    _audit(user_id, "style_create", style["style_id"])
    return style


@router.patch("/{style_id}")
async def update_style(style_id: str, request: Request, body: StyleUpdate):
    user_id = _user_id(request)
    if style_id.startswith("preset:"):
        raise HTTPException(status_code=400, detail="Presets cannot be modified.")
    updated = style_service.update_style(style_id, user_id, body.model_dump(exclude_none=True))
    if updated is None:
        raise HTTPException(status_code=404, detail="Style not found.")
    _audit(user_id, "style_update", style_id)
    return updated


@router.delete("/{style_id}")
async def delete_style(style_id: str, request: Request):
    user_id = _user_id(request)
    if style_id.startswith("preset:"):
        raise HTTPException(status_code=400, detail="Presets cannot be deleted.")
    if not style_service.delete_style(style_id, user_id):
        raise HTTPException(status_code=404, detail="Style not found.")
    _audit(user_id, "style_delete", style_id)
    return {"deleted": True}


@router.put("/default")
async def set_default(request: Request, body: DefaultStyle):
    user_id = _user_id(request)
    if body.style_id is not None:
        resolved = style_service.resolve_style(body.style_id, user_id)
        if resolved is None:
            raise HTTPException(status_code=404, detail="Style not found.")
    style_service.set_default_style(user_id, body.style_id)
    _audit(user_id, "style_set_default", body.style_id or "none")
    return {"default_style_id": body.style_id}
