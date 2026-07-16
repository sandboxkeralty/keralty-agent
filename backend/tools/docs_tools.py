from google.adk.tools import ToolContext
from services.docs import DocsService
from tools._auth import _credentials
from tools._audit import _audit
from tools._approval import _require_approval
from typing import Optional

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
    gate = _require_approval(tool_context, document_id)
    if gate is not None:
        return gate
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


async def docs_create(title: str, tool_context: ToolContext, content: Optional[str] = None,
                      include_signature: bool = False, include_logo: bool = False) -> dict:
    """Creates a new Google Doc, optionally writing initial content to it.

    Args:
        title: The title of the new document.
        content: Optional initial content to write into the document.
        include_signature: Set to True for documents that should be signed
            (letters, memos, official communications) — appends the user's
            active signature (text + logo) at the end automatically. The
            content itself must NOT contain a signature or name/role
            placeholders. Leave False for reports, minutes or analyses.
        include_logo: Set to True for formal/official documents (letters,
            memos, communications) or when the user asks for the corporate
            logo — inserts the authorized Keralty logo at the top. Leave
            False for plain notes, reports or analyses.
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

        if include_logo:
            DocsService.insert_logo_header(doc_id, credentials=creds)

        if include_signature:
            try:
                from services.signature_service import resolve_active
                state = getattr(tool_context, "state", {}) if tool_context else {}
                user_id = state.get("user_id")
                sig = resolve_active(user_id) if user_id else None
                if sig:
                    DocsService.append_signature(
                        doc_id, sig.get("content", ""),
                        logo_url=sig.get("logo_url") or None, credentials=creds,
                    )
            except Exception as e:
                print(f"[docs_create] signature append failed: {e}", flush=True)

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
