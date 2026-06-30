from google.adk.tools import ToolContext
from services.drive import DriveService
from tools._auth import _credentials
from typing import Optional

async def drive_read(file_id: str, tool_context: ToolContext) -> dict:
    """Reads the text content of a Google Drive document.

    Args:
        file_id: The ID of the document to read.
    """
    text = DriveService.read_document_text(file_id, credentials=_credentials(tool_context))
    return {"status": "success", "text": text}

async def drive_search(query: Optional[str] = None, limit: int = 10, tool_context: Optional[ToolContext] = None) -> dict:
    """Searches Google Drive for documents matching a query.

    Args:
        query: Optional search query to filter documents by name.
        limit: Maximum number of results to return.
    """
    results = DriveService.list_documents(query=query, limit=limit, credentials=_credentials(tool_context))
    return {"status": "success", "results": results}
