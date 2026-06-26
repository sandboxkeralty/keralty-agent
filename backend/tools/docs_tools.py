from google.adk.tools import ToolContext

async def docs_get(document_id: str, tool_context: ToolContext) -> dict:
    """Gets the content of a Google Doc.
    
    Args:
        document_id: The ID of the document.
    """
    return {"status": "success", "content": "Sample doc content"}

async def docs_update(document_id: str, content: str, tool_context: ToolContext) -> dict:
    """Updates the content of a Google Doc.
    
    Args:
        document_id: The ID of the document.
        content: The new content to append or replace.
    """
    return {"status": "success", "updated": True}
