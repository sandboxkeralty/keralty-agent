from google.adk.tools import ToolContext
from services.docs import DocsService
from services.firestore import FirestoreService
from tools._auth import _credentials
import uuid

async def docs_get(document_id: str, tool_context: ToolContext) -> dict:
    """Gets the content of a Google Doc.

    Args:
        document_id: The ID of the document.
    """
    try:
        creds = _credentials(tool_context)
        doc = DocsService.get_document(document_id, credentials=creds)
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
    task_id = str(uuid.uuid4())
    user_id = tool_context.session.user_id if getattr(tool_context, "session", None) else "sandbox-user"

    FirestoreService.create_task(task_id, {
        "type": "docs_update",
        "document_id": document_id,
        "content": content,
        "status": "pending",
        "user_id": user_id
    })
    return {"status": "pending_approval", "task_id": task_id, "message": "Task submitted for user approval"}

async def docs_create(title: str, tool_context: ToolContext) -> dict:
    """Creates a new Google Doc and shares it with the requesting user.

    Args:
        title: The title of the new document.
    """
    try:
        creds = _credentials(tool_context)
        doc_id = DocsService.create_document(title, credentials=creds)
        url = f"https://docs.google.com/document/d/{doc_id}/edit"

        # Share with the session user so the doc appears in their Drive
        user_id = getattr(getattr(tool_context, 'session', None), 'user_id', None)
        share_target = user_id if (user_id and '@' in str(user_id)) else 'sandboxkeralty@gmail.com'
        try:
            DocsService.share_document(doc_id, share_target, credentials=creds)
        except Exception:
            pass  # sharing failure is non-fatal

        return {"status": "success", "document_id": doc_id, "url": url}
    except Exception as e:
        print(f"[docs_create] ERROR: {type(e).__name__}: {e}", flush=True)
        return {"status": "error", "message": str(e)}
