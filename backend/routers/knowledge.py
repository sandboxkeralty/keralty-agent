from fastapi import APIRouter, HTTPException, Depends
from typing import List, Dict
from config import settings

router = APIRouter(prefix="/knowledge", tags=["knowledge"])

def check_admin_enabled():
    if not settings.ADMIN_PANEL_ENABLED:
        raise HTTPException(status_code=403, detail="Admin panel is disabled.")

@router.post("/documents", dependencies=[Depends(check_admin_enabled)])
def upload_kb_document(document: dict):
    # Process document upload and index in Vertex AI RAG / GCS
    # Store metadata in Firestore kb_documents
    return {"status": "success", "message": "Document uploaded and re-indexed"}

@router.get("/documents", dependencies=[Depends(check_admin_enabled)])
def list_kb_documents():
    return {"documents": []}

@router.delete("/documents/{doc_id}", dependencies=[Depends(check_admin_enabled)])
def delete_kb_document(doc_id: str):
    return {"status": "success", "message": "Document deleted"}
