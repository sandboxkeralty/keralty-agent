"""Per-executive email/document signatures.

Mirrors the writing-styles feature (style_service.py): per-user Firestore docs
in the `signatures` collection, an active-signature pointer on the user doc,
and a `{signature?}` prompt note injected per turn by routers/chat.py.

Unlike styles, the signature itself is NEVER rendered by the model — tools
append it server-side (GmailProvider.create_draft, DocsService.append_signature)
so the text is verbatim and the logo image actually renders. The prompt note
only tells agents a signature exists and that they must not write their own.
"""

import html
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from services.firestore import db

_COLLECTION = "signatures"

MAX_LABEL_CHARS = 60
MAX_CONTENT_CHARS = 1000
ALLOWED_LOGO_EXTENSIONS = {"png", "jpg", "jpeg"}
MAX_LOGO_BYTES = 2 * 1024 * 1024


def list_user_signatures(user_id: str) -> List[Dict[str, Any]]:
    docs = db.collection(_COLLECTION).where("user_id", "==", user_id).stream()
    sigs = [d.to_dict() for d in docs]
    sigs.sort(key=lambda s: s.get("created_at") or "", reverse=True)
    return sigs


def create_signature(user_id: str, label: str, content: str,
                     logo_url: Optional[str] = None) -> Dict[str, Any]:
    now = datetime.now(timezone.utc).isoformat()
    sig = {
        "signature_id": str(uuid.uuid4()),
        "user_id": user_id,
        "label": label[:MAX_LABEL_CHARS],
        "content": content[:MAX_CONTENT_CHARS],
        "logo_url": logo_url or "",
        "created_at": now,
        "updated_at": now,
    }
    db.collection(_COLLECTION).document(sig["signature_id"]).set(sig)
    return sig


def update_signature(signature_id: str, user_id: str,
                     updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    ref = db.collection(_COLLECTION).document(signature_id)
    doc = ref.get()
    if not doc.exists or doc.to_dict().get("user_id") != user_id:
        return None
    allowed: Dict[str, Any] = {}
    if updates.get("label"):
        allowed["label"] = str(updates["label"])[:MAX_LABEL_CHARS]
    if updates.get("content"):
        allowed["content"] = str(updates["content"])[:MAX_CONTENT_CHARS]
    if "logo_url" in updates and updates["logo_url"] is not None:
        allowed["logo_url"] = str(updates["logo_url"])
    if not allowed:
        return doc.to_dict()
    allowed["updated_at"] = datetime.now(timezone.utc).isoformat()
    ref.update(allowed)
    return ref.get().to_dict()


def delete_signature(signature_id: str, user_id: str) -> bool:
    ref = db.collection(_COLLECTION).document(signature_id)
    doc = ref.get()
    if not doc.exists or doc.to_dict().get("user_id") != user_id:
        return False
    ref.delete()
    # An active pointer at a deleted signature must not linger.
    if get_active_signature_id(user_id) == signature_id:
        set_active_signature(user_id, None)
    return True


def get_active_signature_id(user_id: str) -> Optional[str]:
    try:
        doc = db.collection("users").document(user_id).get()
        if doc.exists:
            return doc.to_dict().get("active_signature_id")
    except Exception as e:
        print(f"[signature_service] get_active_signature_id failed: {e}")
    return None


def set_active_signature(user_id: str, signature_id: Optional[str]) -> None:
    # merge=True is load-bearing: .set() without merge would wipe the user's
    # stored google_credentials (same trap as style_service.set_default_style).
    db.collection("users").document(user_id).set(
        {"active_signature_id": signature_id}, merge=True
    )


def resolve_active(user_id: str) -> Optional[Dict[str, Any]]:
    """Returns the user's active signature dict, or None.

    Never raises: a missing/deleted/foreign signature degrades to "no
    signature" — a lookup failure must never break a chat turn or a draft.
    """
    try:
        sig_id = get_active_signature_id(user_id)
        if not sig_id:
            return None
        doc = db.collection(_COLLECTION).document(sig_id).get()
        if not doc.exists:
            return None
        data = doc.to_dict()
        if data.get("user_id") != user_id:
            return None
        return data
    except Exception as e:
        print(f"[signature_service] resolve_active failed: {e}")
        return None


def format_signature_note(sig: Dict[str, Any]) -> str:
    """Prompt note injected via session.state["signature"] / {signature?}.

    Deliberately does NOT contain the signature body for the model to copy —
    tools append the real signature server-side. Braces are stripped from
    user text (same defence as style_service.format_style_block).
    """
    def _safe(text: str) -> str:
        return (text or "").replace("{", "(").replace("}", ")")

    return (
        f"# FIRMA ACTIVA DEL USUARIO: {_safe(sig.get('label', ''))}\n"
        "El usuario tiene una firma personalizada configurada. Las herramientas la añaden "
        "AUTOMÁTICAMENTE al final de los correos (email_draft) y, si lo solicitas con "
        "include_signature=true, de los Google Docs (docs_create). Por lo tanto: NUNCA "
        "escribas tú una firma, un nombre/cargo de cierre ni placeholders tipo "
        "(Tu Nombre/Cargo) al final del contenido — quedaría duplicada. Termina el cuerpo "
        "con la despedida (p. ej. \"Saludos cordiales,\") y nada más."
    )


def build_html_signature(sig: Dict[str, Any]) -> str:
    """HTML fragment appended to the HTML part of a Gmail draft."""
    lines = [html.escape(l) for l in (sig.get("content") or "").splitlines() if l.strip()]
    parts = ["<br>".join(lines)]
    if sig.get("logo_url"):
        parts.append(
            f'<img src="{html.escape(sig["logo_url"], quote=True)}" '
            'alt="" style="max-height:60px;margin-top:8px;">'
        )
    return "<br>".join(p for p in parts if p)
