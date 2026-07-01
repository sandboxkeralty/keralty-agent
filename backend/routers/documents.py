from fastapi import APIRouter, Query, Response, HTTPException, Request
from services.drive import DriveService
from tools._auth import _credentials

router = APIRouter(prefix="/documents", tags=["documents"])

@router.get("/")
def list_documents(q: str = Query(None), limit: int = 10):
    files = DriveService.list_documents(query=q, limit=limit)
    return {"files": files}

@router.get("/{file_id}/text")
def read_document_text(file_id: str, request: Request):
    """Returns the text content of a Drive document for context injection."""
    text = DriveService.read_document_text(file_id)
    if not text:
        raise HTTPException(status_code=404, detail="Document not found or unreadable")
    return {"file_id": file_id, "text": text}

@router.get("/{file_id}/pdf")
def export_document_pdf(file_id: str):
    try:
        pdf_bytes = DriveService.export_pdf(file_id)
        return Response(content=pdf_bytes, media_type="application/pdf", headers={
            "Content-Disposition": f"attachment; filename=document_{file_id}.pdf"
        })
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

