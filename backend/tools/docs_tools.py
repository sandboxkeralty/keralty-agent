from google.adk.tools import ToolContext
from services.docs import DocsService
from services.firestore import FirestoreService
import uuid

async def docs_get(document_id: str, tool_context: ToolContext) -> dict:
    """Gets the content of a Google Doc.
    
    Args:
        document_id: The ID of the document.
    """
    try:
        doc = DocsService.get_document(document_id)
        # Simplify the representation for the LLM
        content = ""
        for item in doc.get('body', {}).get('content', []):
            if 'paragraph' in item:
                for elem in item['paragraph'].get('elements', []):
                    if 'textRun' in elem:
                        content += (elem['textRun']['content'] or '')
        return {"status": "success", "content": content}
    except Exception as e:
        return {"status": "error", "message": str(e)}

async def docs_update(document_id: str, content: str, tool_context: ToolContext) -> dict:
    """Updates the content of a Google Doc. This requires human approval.
    
    Args:
        document_id: The ID of the document.
        content: The new content to append.
    """
    # Create a pending task for approval
    task_id = str(uuid.uuid4())
    user_id = tool_context.session.user_id if getattr(tool_context, "session", None) else "sandbox-user"
    
    FirestoreService.create_task(task_id, {
        "type": "docs_update",
        "document_id": document_id,
        "content": content,
        "status": "pending",
        "user_id": user_id
    })
    
    # Normally we would yield an ADK Pause/HITL event here.
    return {"status": "pending_approval", "task_id": task_id, "message": "Task submitted for user approval"}

async def docs_create(title: str, tool_context: ToolContext) -> dict:
    """Creates a new Google Doc.
    
    Args:
        title: The title of the new document.
    """
    try:
        doc_id = DocsService.create_document(title)
        return {"status": "success", "document_id": doc_id}
    except Exception as e:
        return {"status": "error", "message": str(e)}
