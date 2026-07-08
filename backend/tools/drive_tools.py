from google.adk.tools import ToolContext
from services.drive import DriveService, DriveReadError
from tools._auth import _credentials
from typing import Optional

async def drive_read(file_id: str, tool_context: ToolContext) -> dict:
    """Reads the text content of a Google Drive document.

    Args:
        file_id: The ID of the document to read.
    """
    try:
        text = DriveService.read_document_text(file_id, credentials=_credentials(tool_context))
    except DriveReadError as e:
        # Return a real error status so the model never treats an error message
        # (unsupported type / too large / API failure) as document content.
        return {"status": "error", "message": str(e)}
    return {"status": "success", "text": text}

async def drive_search(query: Optional[str] = None, limit: int = 10, file_type: Optional[str] = None,
                        tool_context: Optional[ToolContext] = None) -> dict:
    """Searches Google Drive for documents matching a query.

    Args:
        query: Optional search query to filter documents by name.
        limit: Maximum number of results to return.
        file_type: Optional filter — one of "document", "presentation", "spreadsheet".
            Omit to search documents and presentations only. Use "spreadsheet" when
            looking for a Google Sheets file by name.
    """
    mime_types = [file_type] if file_type else None
    try:
        results = DriveService.list_documents(query=query, limit=limit, mime_types=mime_types,
                                               credentials=_credentials(tool_context))
    except Exception as e:
        return {"status": "error", "message": str(e)}
    return {"status": "success", "results": results}
