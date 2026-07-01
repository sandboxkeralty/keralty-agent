"""Knowledge Base management endpoints.

POST   /knowledge/documents          — upload + ingest a document
GET    /knowledge/documents          — list all indexed documents
DELETE /knowledge/documents/{doc_id} — delete document and its chunks
"""

import os
from typing import Dict, Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile

from config import settings
from services.rag.store import list_docs, delete_doc_chunks, delete_doc_metadata

router = APIRouter(prefix="/knowledge", tags=["knowledge"])

_ALLOWED_TYPES = {"pdf", "docx", "doc", "txt", "csv", "md"}


def _check_admin(request: Request):
    if not settings.ADMIN_PANEL_ENABLED:
        raise HTTPException(status_code=403, detail="Admin panel is disabled.")


def _filetype(filename: str) -> str:
    return filename.rsplit(".", 1)[-1].lower() if "." in filename else "txt"


@router.post("/documents", dependencies=[Depends(_check_admin)])
async def upload_document(
    file: UploadFile = File(...),
    description: str = Form(""),
) -> Dict[str, Any]:
    """Upload and ingest a document into the Keralty Knowledge Base."""
    ft = _filetype(file.filename or "")
    if ft not in _ALLOWED_TYPES:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported file type '{ft}'. Allowed: {', '.join(sorted(_ALLOWED_TYPES))}",
        )

    data = await file.read()
    if len(data) > 50 * 1024 * 1024:  # 50 MB guard
        raise HTTPException(status_code=413, detail="File exceeds 50 MB limit.")

    try:
        from services.rag.ingestion import ingest_document
        result = await ingest_document(
            data=data,
            filename=file.filename or "document",
            filetype=ft,
        )
        return {"status": "success", **result}
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {e}")


@router.get("/documents", dependencies=[Depends(_check_admin)])
def list_documents() -> Dict[str, Any]:
    """List all documents indexed in the Knowledge Base."""
    docs = list_docs()
    return {"documents": docs, "count": len(docs)}


@router.delete("/documents/{doc_id}", dependencies=[Depends(_check_admin)])
def delete_document(doc_id: str) -> Dict[str, Any]:
    """Delete a document and all its chunks from the Knowledge Base."""
    chunk_count = delete_doc_chunks(doc_id)
    delete_doc_metadata(doc_id)

    # Invalidate retriever cache
    from services.rag.retriever import invalidate_cache
    invalidate_cache()

    return {
        "status": "success",
        "doc_id": doc_id,
        "chunks_deleted": chunk_count,
    }
