"""Shared follow-up draft generation logic.

Used by both the ADK EmailAgent tool (tools/email_tools.py, has a tool_context)
and the plain REST endpoint in routers/email.py (no tool_context, has a
request.state.user instead) — the actual draft-creation logic is identical for
both callers, so it lives here once instead of being duplicated.
"""

from services.firestore import db
from services.email.gmail_provider import GmailProvider


def generate_followup_draft(tracking_id: str, credentials=None) -> dict:
    """Looks up a tracking record, builds a follow-up reply draft referencing
    the original message, and returns {draft_id, subject, to}.

    Raises ValueError if the tracking record doesn't exist.
    """
    doc = db.collection("email_tracking").document(tracking_id).get()
    if not doc.exists:
        raise ValueError(f"Tracking record {tracking_id} not found")
    tracking = doc.to_dict()
    message_id = tracking.get("message_id")

    to = tracking.get("to", "")
    subject = tracking.get("subject", "")
    thread_id = None

    try:
        headers = GmailProvider.get_message_headers(message_id, credentials=credentials)
        thread_id = headers.get("thread_id") or None
        to = headers.get("to") or to
        subject = headers.get("subject") or subject
    except Exception as lookup_err:
        print(f"[followup_service] original lookup failed: {lookup_err}")

    reply_subject = (
        subject if subject.lower().startswith("re:")
        else f"Re: {subject}" if subject else "Seguimiento"
    )

    body = (
        "Hola,\n\nQuería hacer seguimiento a mi correo anterior. "
        "Quedo atento a tus comentarios cuando tengas oportunidad.\n\nSaludos cordiales."
    )
    draft_id = GmailProvider.create_draft(
        to=to, subject=reply_subject, body=body, thread_id=thread_id, credentials=credentials
    )
    return {"draft_id": draft_id, "subject": reply_subject, "to": to}
