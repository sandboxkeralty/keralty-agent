import hashlib
import uuid
from datetime import datetime, timedelta, timezone

from google.adk.tools import ToolContext

from config import settings
from services.email.gmail_provider import GmailProvider
from tools._auth import _credentials


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
    """Creates a draft email. Does NOT send it."""
    try:
        draft_id = GmailProvider.create_draft(
            to=to, subject=subject, body=body, credentials=_credentials(tool_context)
        )
        return {"status": "success", "draft_id": draft_id}
    except Exception as e:
        return {"status": "error", "error": str(e)}


async def email_send(draft_id: str, tool_context: ToolContext) -> dict:
    """Sends a previously created draft. Requires explicit user approval."""
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
    """Tracks a sent message for follow-up after EMAIL_TRACKING_FOLLOWUP_DAYS days."""
    try:
        from services.firestore import FirestoreService, db
        state = getattr(tool_context, "state", {}) if tool_context else {}
        user_id = state.get("user_id") or "unknown"
        now = datetime.now(timezone.utc)
        tracking_id = str(uuid.uuid4())
        deadline = now + timedelta(days=settings.EMAIL_TRACKING_FOLLOWUP_DAYS)
        db.collection("email_tracking").document(tracking_id).set({
            "tracking_id": tracking_id,
            "message_id": message_id,
            "user_id": user_id,
            "deadline": deadline,
            "status": "waiting",
            "created_at": now,
        })
        return {"status": "success", "tracking_id": tracking_id, "tracking": True}
    except Exception as e:
        return {"status": "error", "error": str(e)}


async def email_get_tracking(tool_context: ToolContext) -> dict:
    """Returns emails being tracked for follow-up that are still awaiting a reply."""
    try:
        from services.firestore import db
        state = getattr(tool_context, "state", {}) if tool_context else {}
        user_id = state.get("user_id") or "unknown"
        docs = db.collection("email_tracking").where(
            "user_id", "==", user_id
        ).where("status", "==", "waiting").stream()
        tracked = [{"tracking_id": doc.id, **doc.to_dict()} for doc in docs]
        return {"status": "success", "tracked_emails": tracked}
    except Exception as e:
        return {"status": "error", "error": str(e)}


async def email_generate_followup(tracking_id: str, tool_context: ToolContext) -> dict:
    """Creates a draft follow-up reply for a tracked email."""
    try:
        from services.firestore import db
        doc = db.collection("email_tracking").document(tracking_id).get()
        if not doc.exists:
            return {"status": "error", "error": f"Tracking record {tracking_id} not found"}
        tracking = doc.to_dict()
        message_id = tracking.get("message_id")

        creds = _credentials(tool_context)

        # Look up the original message to recover the recipient, subject and thread.
        to = ""
        subject = "Follow-up"
        thread_id = None
        try:
            from services.email.gmail_provider import get_gmail_service, _header
            svc = get_gmail_service(creds)
            original = svc.users().messages().get(
                userId="me", id=message_id, format="metadata",
                metadataHeaders=["Subject", "To", "From"]
            ).execute()
            headers = original.get("payload", {}).get("headers", [])
            thread_id = original.get("threadId")
            orig_subject = _header(headers, "Subject")
            to = _header(headers, "To")
            subject = orig_subject if orig_subject.lower().startswith("re:") else f"Re: {orig_subject}"
        except Exception as lookup_err:
            print(f"[email_generate_followup] original lookup failed: {lookup_err}")

        body = (
            "Hola,\n\nQuería hacer seguimiento a mi correo anterior. "
            "Quedo atento a tus comentarios cuando tengas oportunidad.\n\nSaludos cordiales."
        )
        draft_id = GmailProvider.create_draft(
            to=to, subject=subject, body=body, thread_id=thread_id, credentials=creds
        )
        return {"status": "success", "draft_id": draft_id}
    except Exception as e:
        return {"status": "error", "error": str(e)}
