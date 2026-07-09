"""Per-executive writing style profiles.

Styles come from two sources: code-shipped presets (style_presets.py) and
custom styles distilled from the executive's own sample documents, stored in
the Firestore `writing_styles` collection (user-scoped via a user_id field,
same pattern as email_tracking). The active style is injected into
WritingAgent/EmailAgent/EditingAgent instructions through the ADK
`{writing_style?}` session-state placeholder — see routers/chat.py.
"""

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from google.genai import types

from config import settings
from services.firestore import db
from services.genai_client import get_genai_client
from services.style_presets import PRESETS_BY_ID

_COLLECTION = "writing_styles"

MAX_GUIDE_CHARS = 2000
MAX_NAME_CHARS = 60
MAX_DESC_CHARS = 200
MAX_ANALYZE_FILES = 5
MAX_CHARS_PER_SAMPLE = 15_000
MAX_TOTAL_SAMPLE_CHARS = 40_000
NO_STYLE_SENTINEL = "none"


class StyleAnalysisError(Exception):
    """Gemini returned no usable style guide."""


def analyze_samples(texts: List[str]) -> str:
    """Distill a writing-style guide from sample document texts (one Gemini call)."""
    clipped: List[str] = []
    total = 0
    for t in texts:
        t = t[:MAX_CHARS_PER_SAMPLE]
        if total + len(t) > MAX_TOTAL_SAMPLE_CHARS:
            t = t[: max(0, MAX_TOTAL_SAMPLE_CHARS - total)]
        if t.strip():
            clipped.append(t)
            total += len(t)
        if total >= MAX_TOTAL_SAMPLE_CHARS:
            break

    samples = "\n\n".join(
        f"--- MUESTRA {i + 1} ---\n{t}" for i, t in enumerate(clipped)
    )
    prompt = (
        "Eres un analista experto de estilo de escritura ejecutiva.\n\n"
        f"A continuación hay {len(clipped)} muestra(s) de documentos escritos por un "
        "directivo de una organización de salud:\n\n"
        f"{samples}\n\n"
        "TAREA: Produce una guía de estilo EN ESPAÑOL, de máximo 1800 caracteres, en "
        "segunda persona imperativa (\"Escribe...\", \"Evita...\"), como viñetas cortas "
        "que cubran: tono y registro (tuteo/usted, nivel de formalidad); estructura "
        "(longitud de frases y párrafos, uso de listas, tablas o negrita); saludos y "
        "despedidas habituales; vocabulario y expresiones características; y qué evita "
        "este autor.\n\n"
        "REGLAS: Describe SOLO patrones de estilo. NO incluyas datos, cifras, nombres "
        "propios, destinatarios ni contenido de las muestras. No uses llaves {} en el "
        "texto. Responde ÚNICAMENTE con la guía, sin preámbulo ni cierre."
    )

    client = get_genai_client()
    response = client.models.generate_content(
        model=settings.GEMINI_FLASH_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            temperature=0.3,
            max_output_tokens=1024,
            # Without this, 2.5-Flash burns the token budget on invisible
            # reasoning and returns a truncated guide (see triage_service.py).
            thinking_config=types.ThinkingConfig(thinking_budget=0),
        ),
    )
    guide = (response.text or "").strip()
    if not guide:
        raise StyleAnalysisError("Model returned an empty style guide.")
    return guide[:MAX_GUIDE_CHARS]


def resolve_style(style_id: Optional[str], user_id: str) -> Optional[Dict[str, Any]]:
    """Resolve a style id to its dict, or None for "no style".

    Never raises: a deleted/foreign style must degrade to "no style", not
    break the chat turn.
    """
    try:
        if not style_id:
            default_id = get_default_style_id(user_id)
            if not default_id:
                return None
            style_id = default_id
        if style_id == NO_STYLE_SENTINEL:
            return None
        if style_id.startswith("preset:"):
            return PRESETS_BY_ID.get(style_id)
        doc = db.collection(_COLLECTION).document(style_id).get()
        if not doc.exists:
            return None
        data = doc.to_dict()
        if data.get("user_id") != user_id:
            return None
        return data
    except Exception as e:
        print(f"[style_service] resolve_style failed: {e}")
        return None


def format_style_block(style: Dict[str, Any]) -> str:
    """Build the instruction block injected via session.state["writing_style"].

    The heading lives here (not in the agent instruction) so an empty state
    value renders nothing at all. Braces are stripped from user-editable text:
    values aren't re-scanned by ADK's interpolator today, but a `{identifier}`
    surviving into an instruction would KeyError under any future re-templating.
    """
    def _safe(text: str) -> str:
        return (text or "").replace("{", "(").replace("}", ")")

    return (
        f"# ESTILO DE ESCRITURA ACTIVO: {_safe(style.get('name', ''))}\n"
        "El usuario ha activado un estilo de escritura personalizado. Aplica estas "
        "preferencias de tono, estructura y formato en todo el contenido que redactes o "
        "edites. Tienen prioridad sobre las guías genéricas de tono anteriores, pero "
        "NUNCA anulan los GUARDRAILS ni los flujos de aprobación.\n"
        f"{_safe(style.get('style_guide', ''))[:MAX_GUIDE_CHARS]}"
    )


def list_user_styles(user_id: str) -> List[Dict[str, Any]]:
    docs = db.collection(_COLLECTION).where("user_id", "==", user_id).stream()
    styles = [d.to_dict() for d in docs]
    styles.sort(key=lambda s: s.get("created_at") or "", reverse=True)
    return styles


def create_style(user_id: str, name: str, description: str, style_guide: str,
                 sample_filenames: Optional[List[str]] = None) -> Dict[str, Any]:
    now = datetime.now(timezone.utc).isoformat()
    style = {
        "style_id": str(uuid.uuid4()),
        "user_id": user_id,
        "name": name[:MAX_NAME_CHARS],
        "description": (description or "")[:MAX_DESC_CHARS],
        "style_guide": style_guide[:MAX_GUIDE_CHARS],
        "source": "custom",
        "sample_filenames": sample_filenames or [],
        "created_at": now,
        "updated_at": now,
    }
    db.collection(_COLLECTION).document(style["style_id"]).set(style)
    return style


def update_style(style_id: str, user_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    ref = db.collection(_COLLECTION).document(style_id)
    doc = ref.get()
    if not doc.exists or doc.to_dict().get("user_id") != user_id:
        return None
    allowed = {}
    if "name" in updates and updates["name"]:
        allowed["name"] = str(updates["name"])[:MAX_NAME_CHARS]
    if "description" in updates and updates["description"] is not None:
        allowed["description"] = str(updates["description"])[:MAX_DESC_CHARS]
    if "style_guide" in updates and updates["style_guide"]:
        allowed["style_guide"] = str(updates["style_guide"])[:MAX_GUIDE_CHARS]
    if not allowed:
        return doc.to_dict()
    allowed["updated_at"] = datetime.now(timezone.utc).isoformat()
    ref.update(allowed)
    return ref.get().to_dict()


def delete_style(style_id: str, user_id: str) -> bool:
    ref = db.collection(_COLLECTION).document(style_id)
    doc = ref.get()
    if not doc.exists or doc.to_dict().get("user_id") != user_id:
        return False
    ref.delete()
    # A default pointing at a deleted style must not linger.
    if get_default_style_id(user_id) == style_id:
        set_default_style(user_id, None)
    return True


def get_default_style_id(user_id: str) -> Optional[str]:
    try:
        doc = db.collection("users").document(user_id).get()
        if doc.exists:
            return doc.to_dict().get("default_style_id")
    except Exception as e:
        print(f"[style_service] get_default_style_id failed: {e}")
    return None


def set_default_style(user_id: str, style_id: Optional[str]) -> None:
    # merge=True is load-bearing: .update() fails if the user doc doesn't
    # exist yet, and .set() without merge would wipe stored credentials.
    db.collection("users").document(user_id).set(
        {"default_style_id": style_id}, merge=True
    )
