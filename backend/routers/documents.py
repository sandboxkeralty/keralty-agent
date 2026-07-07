from fastapi import APIRouter, Query, Response, HTTPException, Request, UploadFile, File
from auth.google_oauth import credentials_from_dict, credentials_to_dict
from services.drive import DriveService
from services.firestore import FirestoreService

router = APIRouter(prefix="/documents", tags=["documents"])

_ALLOWED_UPLOAD_TYPES = {"pdf", "docx", "doc", "txt", "csv", "md"}
_MAX_UPLOAD_BYTES = 50 * 1024 * 1024


def _credentials_for_user(user_id: str):
    creds_dict = FirestoreService.get_user_credentials(user_id)
    if not creds_dict:
        return None
    creds = credentials_from_dict(creds_dict)
    if creds.expired and creds.refresh_token:
        try:
            from google.auth.transport.requests import Request as GRequest
            creds.refresh(GRequest())
            FirestoreService.store_user_credentials(user_id, {}, credentials_to_dict(creds))
        except Exception as e:
            print(f"[documents] token refresh failed: {e}")
    return creds


def _creds_from_request(request: Request):
    user = getattr(request.state, "user", {})
    user_id = user.get("email") or user.get("uid") or "sandbox-user"
    return _credentials_for_user(user_id)


@router.get("/")
def list_documents(request: Request, q: str = Query(None), limit: int = 10):
    creds = _creds_from_request(request)
    files = DriveService.list_documents(query=q, limit=limit, credentials=creds)
    return {"files": files}

@router.get("/{file_id}/text")
def read_document_text(file_id: str, request: Request):
    """Returns the text content of a Drive document for context injection."""
    creds = _creds_from_request(request)
    text = DriveService.read_document_text(file_id, credentials=creds)
    if not text:
        raise HTTPException(status_code=404, detail="Document not found or unreadable")
    return {"file_id": file_id, "text": text}

@router.get("/{file_id}/pdf")
def export_document_pdf(file_id: str, request: Request):
    creds = _creds_from_request(request)
    try:
        pdf_bytes = DriveService.export_pdf(file_id, credentials=creds)
        return Response(content=pdf_bytes, media_type="application/pdf", headers={
            "Content-Disposition": f"attachment; filename=document_{file_id}.pdf"
        })
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/upload")
async def upload_document(file: UploadFile = File(...)):
    """Extracts text from a locally uploaded file for ad-hoc chat attachment.

    Does NOT persist to the Knowledge Base (no chunking/embedding/Firestore/GCS
    writes) — use POST /knowledge/documents for that. This endpoint is for
    one-off files a user attaches to a single chat turn.
    """
    ft = file.filename.rsplit(".", 1)[-1].lower() if file.filename and "." in file.filename else "txt"
    if ft not in _ALLOWED_UPLOAD_TYPES:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported file type '{ft}'. Allowed: {', '.join(sorted(_ALLOWED_UPLOAD_TYPES))}",
        )

    data = await file.read()
    if len(data) > _MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File exceeds 50 MB limit.")

    from services.rag.ingestion import extract_text
    try:
        text = extract_text(data, ft)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Could not extract text from '{file.filename}': {e}")

    if not text.strip():
        raise HTTPException(status_code=422, detail=f"No extractable text found in '{file.filename}'.")

    return {"filename": file.filename, "text": text}

