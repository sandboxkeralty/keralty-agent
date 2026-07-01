from google.adk.tools import ToolContext
from services.firestore import FirestoreService
import uuid

async def approval_create(task_description: str, document_id: str, changes_summary: str, tool_context: ToolContext) -> dict:
    """Creates an approval request for a critical action like writing to Workspace.
    
    Args:
        task_description: Description of the task that requires approval.
        document_id: The ID of the document to modify.
        changes_summary: Summary of changes to be applied.
    """
    task_id = str(uuid.uuid4())
    state = getattr(tool_context, "state", {}) if tool_context else {}
    user_id = state.get("user_id") or "sandbox-user"
    
    FirestoreService.create_task(task_id, {
        "type": "generic_approval",
        "description": task_description,
        "document_id": document_id,
        "changes_summary": changes_summary,
        "status": "pending",
        "user_id": user_id
    })
    
    return {"status": "pending_approval", "task_id": task_id, "state": "pending"}
