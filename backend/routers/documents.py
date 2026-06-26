from fastapi import APIRouter, Query, Response, HTTPException
from services.drive import DriveService

router = APIRouter(prefix="/documents", tags=["documents"])

@router.get("/")
def list_documents(q: str = Query(None), limit: int = 10):
    files = DriveService.list_documents(query=q, limit=limit)
    return {"files": files}

@router.get("/{file_id}/pdf")
def export_document_pdf(file_id: str):
    try:
        pdf_bytes = DriveService.export_pdf(file_id)
        return Response(content=pdf_bytes, media_type="application/pdf", headers={
            "Content-Disposition": f"attachment; filename=document_{file_id}.pdf"
        })
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

