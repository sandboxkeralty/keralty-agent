"""Dashboard reply-draft generation for Correo Ejecutivo v2 (Phase 2).

Generates a reply draft for a thread from a chosen action (accept / decline /
ask for more info / delegate / free instruction), honoring the executive's
default writing style and active signature, defaulting the language to the
sender's. The draft is ALWAYS created in Gmail for review — nothing is sent
from here; sending goes through the HITL-gated endpoint.
"""

from typing import Any, Dict, List, Optional

from config import settings
from services.email.gmail_provider import GmailProvider
from services.genai_client import get_genai_client

_ACTION_INSTRUCTIONS = {
    "aceptar": "Responde ACEPTANDO la solicitud o propuesta del remitente, con tono positivo y concreto.",
    "declinar": "Responde DECLINANDO cortésmente la solicitud o propuesta, agradeciendo y dejando la puerta abierta.",
    "mas_info": "Responde PIDIENDO MÁS INFORMACIÓN: identifica qué datos faltan para poder decidir y solicítalos con claridad.",
    "delegar": "Responde indicando que DELEGARÁS el tema al responsable adecuado del equipo y que esa persona dará seguimiento.",
    "libre": "",
}

_MODIFIER_INSTRUCTIONS = {
    "shorter": "Hazlo MÁS CORTO: máximo 4-5 líneas.",
    "more_formal": "Usa un tono MÁS FORMAL e institucional.",
}


def _last_inbound(messages: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    inbound = [m for m in messages if "SENT" not in (m.get("label_ids") or [])]
    return inbound[-1] if inbound else None


def _thread_context(messages: List[Dict[str, Any]], limit: int = 4) -> str:
    parts = []
    for m in sorted(messages, key=lambda x: x.get("internal_date", 0))[-limit:]:
        who = "[EJECUTIVO]" if "SENT" in (m.get("label_ids") or []) else "[REMITENTE]"
        text = (m.get("body") or m.get("snippet") or "").strip()[:1200]
        parts.append(f"{who} {m.get('from', '')}: {text}")
    return "\n\n".join(parts)


def _generate_body(context: str, resumen: str, action: str, instruction: str,
                   language: Optional[str], modifiers: List[str],
                   style_block: str) -> str:
    """Raises on failure — a reply draft with a template fallback would be
    worse than an honest error the UI can show."""
    from google.genai import types

    if language == "en":
        lang_rule = "Escribe la respuesta en INGLÉS."
    elif language == "es":
        lang_rule = "Escribe la respuesta en ESPAÑOL."
    else:
        lang_rule = "Escribe la respuesta en el MISMO idioma del último mensaje del remitente."

    directives = [_ACTION_INSTRUCTIONS.get(action, ""), (instruction or "").strip()[:500]]
    directives += [_MODIFIER_INSTRUCTIONS[m] for m in modifiers if m in _MODIFIER_INSTRUCTIONS]
    directive_text = "\n".join(d for d in directives if d)

    prompt = (
        "Eres el asistente de un ejecutivo de Keralty (empresa internacional de salud). "
        "Redacta el CUERPO de una respuesta de correo en su nombre.\n\n"
        f"Hilo de correo (del más antiguo al más reciente):\n{context}\n\n"
        + (f"Resumen del hilo: {resumen}\n\n" if resumen else "")
        + f"Instrucciones para la respuesta:\n{directive_text}\n{lang_rule}\n\n"
        "Reglas: tono ejecutivo profesional. NO incluyas asunto ni firma ni nombre/cargo de "
        "cierre (la firma se añade automáticamente); termina con la despedida (p. ej. "
        "\"Saludos cordiales,\"). NO uses placeholders sin completar como [nombre] o [fecha] — "
        "si no tienes un dato, omítelo. Es un correo de TEXTO PLANO: no uses formato Markdown "
        "(nada de **negritas**, # títulos ni listas con guiones). Responde con SOLO el cuerpo "
        "del correo.\n"
        + (f"\n{style_block}\n" if style_block else "")
    )

    client = get_genai_client()
    response = client.models.generate_content(
        model=settings.GEMINI_FLASH_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            temperature=0.4,
            max_output_tokens=1024,
            # Mandatory on short direct calls — see triage/followup services.
            thinking_config=types.ThinkingConfig(thinking_budget=0),
        ),
    )
    body = (response.text or "").strip()
    if not body:
        raise RuntimeError("empty reply body from model")
    return body


def generate_reply_draft(user_id: str, thread_id: str, action: str,
                         instruction: str = "", language: Optional[str] = None,
                         modifiers: Optional[List[str]] = None,
                         previous_draft_id: Optional[str] = None,
                         resumen: str = "", credentials=None) -> Dict[str, Any]:
    """Builds the reply draft in Gmail and returns everything the UI needs to
    edit/regenerate/send it later. Raises ValueError when the thread has no
    inbound message to reply to."""
    thread = GmailProvider.get_thread(thread_id, credentials=credentials)
    messages = thread.get("messages", [])
    target = _last_inbound(messages)
    if not target:
        raise ValueError("Thread has no inbound message to reply to")

    to = target.get("from", "")
    subject = target.get("subject", "") or ""
    reply_subject = subject if subject.lower().startswith("re:") else (f"Re: {subject}" if subject else "Re:")
    in_reply_to = target.get("rfc822_message_id") or None
    references = " ".join(x for x in [target.get("references"), target.get("rfc822_message_id")] if x) or None

    # Executive's default writing style (optional, never blocking).
    style_block = ""
    try:
        from services.style_service import get_default_style_id, resolve_style, format_style_block
        style = resolve_style(get_default_style_id(user_id), user_id)
        if style:
            style_block = format_style_block(style)
    except Exception as e:
        print(f"[reply_service] style lookup failed: {e}")

    body = _generate_body(_thread_context(messages), resumen, action, instruction,
                          language, modifiers or [], style_block)

    signature = None
    try:
        from services.signature_service import resolve_active
        signature = resolve_active(user_id)
    except Exception as e:
        print(f"[reply_service] signature lookup failed: {e}")

    draft_id = GmailProvider.create_draft(
        to=to, subject=reply_subject, body=body, thread_id=thread_id,
        credentials=credentials, signature=signature,
        in_reply_to=in_reply_to, references=references,
    )

    # Regenerate/shorter/formal/language all create a fresh draft — the stale
    # one must not linger in Gmail (or worse, get approved and sent).
    if previous_draft_id:
        try:
            GmailProvider.delete_draft(previous_draft_id, credentials=credentials)
        except Exception as e:
            print(f"[reply_service] previous draft cleanup failed: {e}")

    return {
        "draft_id": draft_id,
        "thread_id": thread_id,
        "to": to,
        "subject": reply_subject,
        "body": body,
        "in_reply_to": in_reply_to,
        "references": references,
        "signature_applied": bool(signature),
    }
