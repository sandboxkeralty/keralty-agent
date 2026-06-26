from google.adk.tools import ToolContext

async def approval_create(task_description: str, document_id: str, changes_summary: str, tool_context: ToolContext) -> dict:
    """Creates an approval request for a critical action like writing to Workspace.
    
    Args:
        task_description: Description of the task that requires approval.
        document_id: The ID of the document to modify.
        changes_summary: Summary of changes to be applied.
    """
    return {"status": "success", "approval_id": "app_12345", "state": "pending"}
