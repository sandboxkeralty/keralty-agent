import hashlib
import uuid
from datetime import datetime, timedelta, timezone

from google.adk.tools import ToolContext

from services.email.gmail_provider import GmailProvider
from tools._auth import _credentials
from tools._approval import _require_approval


async def email_list(account_id: str = "primary", folder: str = "inbox", max_results: int = 50, tool_context: ToolContext = None) -> dict:
    """Lists email threads from a folder (default: inbox)."""
    try:
        threads = GmailProvider.list_threads(
            max_results=max_results, folder=folder, credentials=_credentials(tool_context)
        )
        return {"status": "success", "emails": threads}
    except Exception as e:
        return {"status": "error", "error": str(e)}


async def email_read(thread_id: str, tool_context: ToolContext) -> dict:
    """Reads the full content of an email thread, including all messages."""
    try:
        thread = GmailProvider.get_thread(thread_id, credentials=_credentials(tool_context))
        return {"status": "success", "thread": thread}
    except Exception as e:
        return {"status": "error", "error": str(e)}


async def email_search(query: str, max_results: int = 10, tool_context: ToolContext = None) -> dict:
    """Searches emails using Gmail query syntax (e.g. 'from:boss subject:urgent')."""
    try:
        results = GmailProvider.search_threads(
            query, max_results=max_results, credentials=_credentials(tool_context)
        )
        return {"status": "success", "results": results}
    except Exception as e:
        return {"status": "error", "error": str(e)}


async def email_summarize_thread(thread_id: str, tool_context: ToolContext) -> dict:
    """Fetches a thread's full content as structured data for the agent to summarize."""
    try:
        thread = GmailProvider.get_thread(thread_id, credentials=_credentials(tool_context))
        return {"status": "success", "thread": thread}
    except Exception as e:
        return {"status": "error", "error": str(e)}


async def email_draft(to: str, subject: str, body: str, tool_context: ToolContext) -> dict:
    """Creates a draft email. Does NOT send it.

    If the user has an active signature configured, it is appended to the draft
    automatically (text + logo, via an HTML part) — the body you pass must NOT
    contain a signature or name/role placeholders.
    """
    try:
        signature = None
        try:
            from services.signature_service import resolve_active
            state = getattr(tool_context, "state", {}) if tool_context else {}
            user_id = state.get("user_id")
            if user_id:
                signature = resolve_active(user_id)
        except Exception as sig_err:
            print(f"[email_draft] signature lookup failed: {sig_err}", flush=True)
        draft_id = GmailProvider.create_draft(
            to=to, subject=subject, body=body,
            credentials=_credentials(tool_context), signature=signature,
        )
        return {"status": "success", "draft_id": draft_id,
                "signature_applied": bool(signature)}
    except Exception as e:
        return {"status": "error", "error": str(e)}


async def email_send(draft_id: str, tool_context: ToolContext) -> dict:
    """Sends a previously created draft. Requires explicit user approval."""
    gate = _require_approval(tool_context, draft_id)
    if gate is not None:
        return gate
    try:
        message_id = GmailProvider.send_draft(draft_id, credentials=_credentials(tool_context))

        # Audit logging of the send action.
        try:
            from services.firestore import FirestoreService
            from models.schemas import AuditEvent
            state = getattr(tool_context, "state", {}) if tool_context else {}
            user_id = state.get("user_id") or "unknown"
            FirestoreService.log_audit_event(AuditEvent(
                event_id=str(uuid.uuid4()),
                user_email_hash=hashlib.sha256(user_id.encode()).hexdigest(),
                action="email_send",
                resource_type="email",
                resource_id=draft_id,
                timestamp=datetime.now(timezone.utc),
            ))
        except Exception as audit_err:
            print(f"[email_send] audit log failed: {audit_err}")

        return {"status": "success", "sent": True, "message_id": message_id}
    except Exception as e:
        return {"status": "error", "error": str(e)}


async def email_track(message_id: str, tool_context: ToolContext) -> dict:
    """Tracks a sent message for follow-up after the user's follow-up window."""
    try:
        from services.email import thread_store
        state = getattr(tool_context, "state", {}) if tool_context else {}
        user_id = state.get("user_id") or "unknown"
        # Per-executive follow-up window (falls back to the global default).
        followup_days = thread_store.get_email_settings(user_id)["followup_days"]
        deadline = datetime.now(timezone.utc) + timedelta(days=followup_days)

        # Capture descriptive info (subject/recipient/thread) at tracking time
        # so the dashboard never shows a raw Gmail message_id, and the v2 scan
        # can link this record to its thread state without extra lookups.
        subject, to, thread_id = "", "", ""
        try:
            headers = GmailProvider.get_message_headers(message_id, credentials=_credentials(tool_context))
            subject, to = headers.get("subject", ""), headers.get("to", "")
            thread_id = headers.get("thread_id", "")
        except Exception as header_err:
            print(f"[email_track] header lookup failed: {header_err}")

        tracking_id = thread_store.create_tracking(
            user_id=user_id, message_id=message_id, thread_id=thread_id,
            subject=subject, to=to, deadline=deadline,
        )
        return {"status": "success", "tracking_id": tracking_id, "tracking": True}
    except Exception as e:
        return {"status": "error", "error": str(e)}


async def email_get_tracking(tool_context: ToolContext) -> dict:
    """Returns emails being tracked for follow-up that are still awaiting a reply."""
    try:
        from services.email import thread_store
        state = getattr(tool_context, "state", {}) if tool_context else {}
        user_id = state.get("user_id") or "unknown"
        tracked = thread_store.get_tracked(user_id, ["waiting", "followup_drafted"])
        return {"status": "success", "tracked_emails": tracked}
    except Exception as e:
        return {"status": "error", "error": str(e)}


async def email_generate_followup(tracking_id: str, tool_context: ToolContext) -> dict:
    """Creates a draft follow-up reply for a tracked email."""
    try:
        from services.email.followup_service import generate_followup_draft
        result = generate_followup_draft(tracking_id, credentials=_credentials(tool_context))
        return {"status": "success", **result}
    except ValueError as e:
        return {"status": "error", "error": str(e)}
    except Exception as e:
        return {"status": "error", "error": str(e)}
