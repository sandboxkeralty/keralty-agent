"""Weekly executive email digest (Phase 3).

Summarizes the week's email_threads state into sections + a short Gemini
narrative, stores it in `email_digests` (in-app view), and — when the user
hasn't opted out — emails it to the executive.

The digest email is the platform's ONE documented HITL exception: it is an
automated send with no per-send approval, allowed because it is strictly a
self-notification (from the user's own Gmail to their own address, we hold no
other sending credentials) whose content is a system-generated report, with a
per-user opt-out (email_settings.digest_email_enabled). Approved by the
product owner July 2026 — see docs/audit-2026-07-remediation.md. It must NEVER
be generalized to other recipients or content.
"""

import html as _html
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from config import settings
from services.email import thread_store
from services.email.gmail_provider import GmailProvider
from services.firestore import db
from services.genai_client import get_genai_client

_DAY_MS = 86_400_000
_COLLECTION = "email_digests"

_TEXTS = {
    "es": {
        "subject": "Tu resumen semanal de correo — Keralty Assistant",
        "title": "Resumen semanal de correo",
        "totals": "Esta semana: {total} hilos · {criticos} críticos · {pendientes} con acción pendiente · {seguimiento} en seguimiento · {resueltos} resueltos",
        "criticals": "Críticos",
        "pending": "Acciones pendientes",
        "followup": "En seguimiento sin respuesta",
        "days": "{days} días sin respuesta",
        "fallback": "Aquí tienes el resumen de la actividad de tu correo esta semana.",
    },
    "en": {
        "subject": "Your weekly email digest — Keralty Assistant",
        "title": "Weekly email digest",
        "totals": "This week: {total} threads · {criticos} critical · {pendientes} pending action · {seguimiento} awaiting reply · {resueltos} resolved",
        "criticals": "Critical",
        "pending": "Pending actions",
        "followup": "Awaiting reply",
        "days": "{days} days without reply",
        "fallback": "Here is the summary of your email activity this week.",
    },
}


def _narrative(sections: Dict[str, Any], locale: str) -> str:
    """2-4 sentence executive intro. Template fallback — a Gemini outage never
    blocks the digest."""
    try:
        from google.genai import types
        lang = "español" if locale == "es" else "inglés"
        client = get_genai_client()
        response = client.models.generate_content(
            model=settings.GEMINI_FLASH_MODEL,
            contents=(
                f"Eres el asistente de un ejecutivo. Escribe en {lang} un párrafo introductorio "
                "(2-4 frases, tono ejecutivo, sin saludos ni despedidas) para su resumen semanal "
                "de correo, destacando lo más relevante de estos datos:\n"
                f"{sections}\n\nResponde con SOLO el párrafo."
            ),
            config=types.GenerateContentConfig(
                temperature=0.3,
                max_output_tokens=300,
                thinking_config=types.ThinkingConfig(thinking_budget=0),
            ),
        )
        text = (response.text or "").strip()
        return text or _TEXTS[locale]["fallback"]
    except Exception as e:
        print(f"[digest_service] narrative generation failed: {e}")
        return _TEXTS[locale]["fallback"]


def _build_sections(docs: List[Dict[str, Any]], now_ms: int) -> Dict[str, Any]:
    def _brief(d: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "subject": d.get("subject", ""),
            "from": d.get("from", ""),
            "to": d.get("to", ""),
            "resumen": d.get("resumen", ""),
            "accion_sugerida": d.get("accion_sugerida", ""),
            "fecha_limite": d.get("fecha_limite"),
            "days_without_reply": (
                max(0, (now_ms - d["last_outbound_at"]) // _DAY_MS)
                if d.get("last_outbound_at") else None
            ),
        }
    criticos = [d for d in docs if d.get("prioridad") == "CRITICO" and d.get("estado_gestion") != "resuelto"]
    pendientes = [d for d in docs if d.get("requiere_accion") and d.get("estado_gestion") != "resuelto"
                  and d.get("prioridad") != "CRITICO"]
    seguimiento = [d for d in docs if d.get("esperando_respuesta") and d.get("estado_gestion") != "pospuesto"]
    resueltos = [d for d in docs if d.get("estado_gestion") == "resuelto"]
    return {
        "totals": {
            "total": len(docs), "criticos": len(criticos), "pendientes": len(pendientes),
            "seguimiento": len(seguimiento), "resueltos": len(resueltos),
        },
        "criticos": [_brief(d) for d in criticos[:10]],
        "pendientes": [_brief(d) for d in pendientes[:10]],
        "seguimiento": [_brief(d) for d in seguimiento[:10]],
    }


def _render_text(sections: Dict[str, Any], narrative: str, locale: str) -> str:
    t = _TEXTS[locale]
    lines = [t["title"], "", narrative, "", t["totals"].format(**sections["totals"]), ""]
    for key, label in (("criticos", t["criticals"]), ("pendientes", t["pending"]),
                       ("seguimiento", t["followup"])):
        items = sections.get(key) or []
        if not items:
            continue
        lines.append(f"— {label} —")
        for item in items:
            extra = ""
            if key == "seguimiento" and item.get("days_without_reply") is not None:
                extra = f" ({t['days'].format(days=item['days_without_reply'])})"
            elif item.get("accion_sugerida"):
                extra = f" — {item['accion_sugerida']}"
            lines.append(f"• {item['subject'] or '(sin asunto)'}{extra}")
        lines.append("")
    return "\n".join(lines)


def _render_html(text: str) -> str:
    from services import brand
    body = _html.escape(text).replace("\n", "<br>")
    logo = brand.logo_for_background("white")
    return (
        f'<div style="font-family:{brand.EMAIL_FONT_STACK};color:#1a1a2e;max-width:640px">'
        f'<img src="{logo}" alt="Keralty" style="height:36px;margin-bottom:12px;">'
        f'<div style="color:{brand.PRIMARY_BLUE};font-weight:bold;font-size:18px;'
        f'margin-bottom:8px;">Keralty Assistant</div>'
        f'{body}</div>'
    )


def generate_digest(user_id: str, credentials=None) -> Dict[str, Any]:
    """Builds and stores the week's digest; emails it unless opted out.
    Returns the stored digest doc (with `emailed: bool`)."""
    user_settings = thread_store.get_email_settings(user_id)
    locale = user_settings.get("locale", "es")
    now_ms = int(time.time() * 1000)
    week_start_ms = now_ms - 7 * _DAY_MS

    docs = thread_store.get_threads(user_id, week_start_ms)
    sections = _build_sections(docs, now_ms)
    narrative = _narrative(sections, locale)

    digest = {
        "digest_id": str(uuid.uuid4()),
        "user_id": user_id,
        "week_start": datetime.fromtimestamp(week_start_ms / 1000, tz=timezone.utc).isoformat(),
        "week_end": datetime.fromtimestamp(now_ms / 1000, tz=timezone.utc).isoformat(),
        "sections": sections,
        "narrative": narrative,
        "locale": locale,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "emailed": False,
    }

    if user_settings.get("digest_email_enabled") and credentials is not None:
        try:
            text = _render_text(sections, narrative, locale)
            GmailProvider.send_message(
                to=user_id, subject=_TEXTS[locale]["subject"], body=text,
                credentials=credentials, html=_render_html(text),
            )
            digest["emailed"] = True
        except Exception as e:
            print(f"[digest_service] digest email failed for {user_id}: {e}")

    db.collection(_COLLECTION).document(digest["digest_id"]).set(digest)
    return digest


def get_latest(user_id: str) -> Optional[Dict[str, Any]]:
    docs = (
        db.collection(_COLLECTION)
        .where("user_id", "==", user_id)
        .order_by("created_at", direction="DESCENDING")
        .limit(1)
        .stream()
    )
    for d in docs:
        return d.to_dict()
    return None
