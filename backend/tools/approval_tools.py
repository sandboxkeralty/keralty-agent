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
    # user_id is the authenticated identity (email) injected into session state by
    # chat.py. It MUST match what the destructive tool later checks via
    # _require_approval, and what tasks.py checks on approve — otherwise the gate
    # can't find the task. No sandbox fallback: an unauthenticated turn shouldn't
    # be able to create an approvable task.
    user_id = state.get("user_id")
    if not user_id:
        return {"status": "error", "error": "No authenticated user in session; cannot create approval."}
    
    FirestoreService.create_task(task_id, {
        "type": "generic_approval",
        "description": task_description,
        "document_id": document_id,
        "changes_summary": changes_summary,
        "status": "pending",
        "user_id": user_id
    })
    
    return {"status": "pending_approval", "task_id": task_id, "state": "pending"}
