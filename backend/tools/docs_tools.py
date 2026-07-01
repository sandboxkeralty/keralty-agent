import uuid
import hashlib
from datetime import datetime, timezone
from google.adk.tools import ToolContext
from services.docs import DocsService
from services.firestore import FirestoreService
from models.schemas import AuditEvent
from tools._auth import _credentials
from typing import Optional

def _audit(tool_context, action: str, resource_type: str, resource_id: str):
    try:
        user_id = getattr(getattr(tool_context, "session", None), "user_id", None) or ""
        FirestoreService.log_audit_event(AuditEvent(
            event_id=str(uuid.uuid4()),
            user_email_hash=hashlib.sha256(user_id.encode()).hexdigest(),
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            timestamp=datetime.now(timezone.utc),
        ))
    except Exception:
        pass

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
    """Appends text content to an existing Google Doc.

    Args:
        document_id: The ID of the document to update.
        content: The text content to append to the document.
    """
    try:
        creds = _credentials(tool_context)
        DocsService.append_text(document_id, content, credentials=creds)
        url = f"https://docs.google.com/document/d/{document_id}/edit"
        _audit(tool_context, "docs_update", "document", document_id)
        return {"status": "success", "document_id": document_id, "url": url,
                "message": "Content written to document successfully."}
    except Exception as e:
        print(f"[docs_update] ERROR: {type(e).__name__}: {e}", flush=True)
        return {"status": "error", "message": str(e)}


async def docs_create(title: str, tool_context: ToolContext, content: Optional[str] = None) -> dict:
    """Creates a new Google Doc, optionally writing initial content to it.

    Args:
        title: The title of the new document.
        content: Optional initial content to write into the document.
    """
    try:
        creds = _credentials(tool_context)
        doc_id = DocsService.create_document(title, credentials=creds)
        url = f"https://docs.google.com/document/d/{doc_id}/edit"

        if content:
            try:
                DocsService.append_text(doc_id, content, credentials=creds)
            except Exception as e:
                print(f"[docs_create] append failed: {e}", flush=True)

        # Share with the session user so the doc appears in their Drive
        user_id = getattr(getattr(tool_context, 'session', None), 'user_id', None)
        share_target = user_id if (user_id and '@' in str(user_id)) else 'sandboxkeralty@gmail.com'
        try:
            DocsService.share_document(doc_id, share_target, credentials=creds)
        except Exception:
            pass

        _audit(tool_context, "docs_create", "document", doc_id)
        return {"status": "success", "document_id": doc_id, "url": url,
                "message": f"Document '{title}' created successfully."}
    except Exception as e:
        print(f"[docs_create] ERROR: {type(e).__name__}: {e}", flush=True)
        return {"status": "error", "message": str(e)}
