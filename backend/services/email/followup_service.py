"""Shared follow-up draft generation logic.

Used by both the ADK EmailAgent tool (tools/email_tools.py, has a tool_context)
and the plain REST endpoint in routers/email.py (no tool_context, has a
request.state.user instead) — the actual draft-creation logic is identical for
both callers, so it lives here once instead of being duplicated.
"""

from config import settings
from services.firestore import db
from services.email.gmail_provider import GmailProvider
from services.genai_client import get_genai_client

_DEFAULT_BODY = (
    "Hola,\n\nQuería hacer seguimiento a mi correo anterior. "
    "Quedo atento a tus comentarios cuando tengas oportunidad.\n\nSaludos cordiales."
)


def _generate_body(subject: str, to: str, snippet: str) -> str:
    """Drafts a short, topic-aware follow-up body via Gemini.

    Falls back to a generic template on any failure — a personalization
    outage should never block creating the draft itself.
    """
    try:
        from google.genai import types

        client = get_genai_client()
        prompt = (
            "Redacta un breve correo de seguimiento ejecutivo en español, tono profesional y "
            "cordial, para retomar contacto sobre un correo anterior que no ha recibido "
            "respuesta.\n"
            f"Asunto original: {subject or '(sin asunto)'}\n"
            f"Destinatario: {to or '(desconocido)'}\n"
            f"Fragmento del correo original: {snippet or '(no disponible)'}\n\n"
            "El seguimiento debe: (1) referenciar brevemente el tema del correo original, "
            "(2) preguntar cordialmente si hay alguna actualización, (3) cerrar con "
            "disposición a ayudar. Máximo 5 líneas. No uses corchetes ni placeholders sin "
            "completar (como '[nombre]' o '[fecha]') — si no tienes un dato, omítelo por "
            "completo en vez de dejar un marcador. Responde con SOLO el cuerpo del correo, "
            "sin asunto ni firma."
        )
        response = client.models.generate_content(
            model=settings.GEMINI_FLASH_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.4,
                max_output_tokens=300,
                # Gemini 2.5 Flash's "thinking" tokens count against
                # max_output_tokens — without disabling it, the model can burn
                # the entire budget on invisible reasoning and return a
                # truncated (or empty) visible response. Confirmed empirically:
                # identical call without this returned finish_reason=MAX_TOKENS
                # and a 4-word cutoff body; with it, a complete draft.
                thinking_config=types.ThinkingConfig(thinking_budget=0),
            ),
        )
        text = (response.text or "").strip()
        return text or _DEFAULT_BODY
    except Exception as e:
        print(f"[followup_service] personalized body generation failed: {e}")
        return _DEFAULT_BODY


def generate_followup_draft(tracking_id: str, credentials=None) -> dict:
    """Looks up a tracking record, builds a follow-up reply draft referencing
    the original message, and returns {draft_id, subject, to, body}.

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
    snippet = ""

    try:
        headers = GmailProvider.get_message_headers(message_id, credentials=credentials)
        thread_id = headers.get("thread_id") or None
        to = headers.get("to") or to
        subject = headers.get("subject") or subject
        snippet = headers.get("snippet", "")
    except Exception as lookup_err:
        print(f"[followup_service] original lookup failed: {lookup_err}")

    reply_subject = (
        subject if subject.lower().startswith("re:")
        else f"Re: {subject}" if subject else "Seguimiento"
    )

    body = _generate_body(subject, to, snippet)
    draft_id = GmailProvider.create_draft(
        to=to, subject=reply_subject, body=body, thread_id=thread_id, credentials=credentials
    )
    return {"draft_id": draft_id, "subject": reply_subject, "to": to, "body": body}
