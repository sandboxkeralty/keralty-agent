from google.adk.tools import ToolContext
from services.drive import DriveService

async def drive_read(file_id: str, tool_context: ToolContext) -> dict:
    """Reads the text content of a Google Drive document.

    Args:
        file_id: The ID of the document to read.
    """
    text = DriveService.read_document_text(file_id)
    return {"status": "success", "text": text}
