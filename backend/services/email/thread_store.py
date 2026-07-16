"""Per-user email thread state for Correo Ejecutivo v2.

One Firestore doc per (user, Gmail thread) in `email_threads` — the persistent
memory that makes the dashboard incremental: summaries/facets are computed once
and reused until the thread's Gmail historyId changes. Doc id is
"{user_id}::{thread_id}", so upserts are idempotent and need no lookup query.

Also centralizes `email_tracking` access (previously raw db.collection() calls
copied across routers/email.py, tools/email_tools.py and followup_service.py)
and the per-user email settings stored on the users doc.

Ownership model mirrors services/signature_service.py: every doc carries
user_id; mutations re-fetch and verify it before writing.
"""

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from config import settings
from services.firestore import db

_COLLECTION = "email_threads"
_TRACKING = "email_tracking"

# Clamp ranges for the per-executive settings (decisions 5/6 of the v2 plan).
_WINDOW_MIN, _WINDOW_MAX = 3, 14
_FOLLOWUP_MIN, _FOLLOWUP_MAX = 1, 14


def _doc_id(user_id: str, thread_id: str) -> str:
    return f"{user_id}::{thread_id}"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# email_threads

def get_threads(user_id: str, since_epoch_ms: int) -> List[Dict[str, Any]]:
    """All thread-state docs in the window, newest first.

    The ONLY indexed query on this collection — requires the composite index
    email_threads(user_id ASC, last_message_internal_date DESC). Facet/view
    filtering happens in memory on the (small) result.
    """
    docs = (
        db.collection(_COLLECTION)
        .where("user_id", "==", user_id)
        .where("last_message_internal_date", ">=", since_epoch_ms)
        .order_by("last_message_internal_date", direction="DESCENDING")
        .stream()
    )
    return [d.to_dict() for d in docs]


def get_thread(user_id: str, thread_id: str) -> Optional[Dict[str, Any]]:
    doc = db.collection(_COLLECTION).document(_doc_id(user_id, thread_id)).get()
    if not doc.exists:
        return None
    data = doc.to_dict()
    return data if data.get("user_id") == user_id else None


def upsert_threads(user_id: str, docs: List[Dict[str, Any]]) -> None:
    """Batched idempotent write. Each doc must carry thread_id; user_id and
    updated_at are stamped here so callers can't write a foreign doc."""
    if not docs:
        return
    now = _now_iso()
    batch = db.batch()
    pending = 0
    for item in docs:
        item = dict(item)
        item["user_id"] = user_id
        item["updated_at"] = now
        item.setdefault("created_at", now)
        ref = db.collection(_COLLECTION).document(_doc_id(user_id, item["thread_id"]))
        batch.set(ref, item, merge=True)
        pending += 1
        if pending >= 450:  # Firestore batch limit is 500 ops; stay clear of it
            batch.commit()
            batch = db.batch()
            pending = 0
    if pending:
        batch.commit()


def update_thread(user_id: str, thread_id: str,
                  updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Ownership-verified partial update. Returns the updated doc, or None if
    the doc doesn't exist or belongs to another user."""
    ref = db.collection(_COLLECTION).document(_doc_id(user_id, thread_id))
    doc = ref.get()
    if not doc.exists or doc.to_dict().get("user_id") != user_id:
        return None
    payload = dict(updates)
    payload["updated_at"] = _now_iso()
    ref.update(payload)
    return ref.get().to_dict()


# ---------------------------------------------------------------------------
# email_tracking (manual follow-up records — chat flow)

def get_tracked(user_id: str, statuses: List[str]) -> List[Dict[str, Any]]:
    docs = (
        db.collection(_TRACKING)
        .where("user_id", "==", user_id)
        .where("status", "in", statuses)
        .stream()
    )
    return [d.to_dict() for d in docs]


def get_tracking(tracking_id: str) -> Optional[Dict[str, Any]]:
    doc = db.collection(_TRACKING).document(tracking_id).get()
    return doc.to_dict() if doc.exists else None


def update_tracking(tracking_id: str, updates: Dict[str, Any]) -> None:
    db.collection(_TRACKING).document(tracking_id).update(updates)


def create_tracking(user_id: str, message_id: str, thread_id: str,
                    subject: str, to: str, deadline: datetime) -> str:
    tracking_id = str(uuid.uuid4())
    db.collection(_TRACKING).document(tracking_id).set({
        "tracking_id": tracking_id,
        "message_id": message_id,
        "thread_id": thread_id,
        "user_id": user_id,
        "subject": subject,
        "to": to,
        "deadline": deadline,
        "status": "waiting",
        "created_at": datetime.now(timezone.utc),
    })
    return tracking_id


# ---------------------------------------------------------------------------
# per-user settings (users/{email}.email_settings — merge=True ALWAYS: a plain
# set() would wipe the user's stored google_credentials)

def _defaults() -> Dict[str, Any]:
    return {
        "window_days": settings.EMAIL_SCAN_WINDOW_DAYS,
        "followup_days": settings.EMAIL_TRACKING_FOLLOWUP_DAYS,
        "digest_email_enabled": True,
        "locale": "es",
    }


def _clamp(value: Any, lo: int, hi: int, fallback: int) -> int:
    try:
        return max(lo, min(hi, int(value)))
    except (TypeError, ValueError):
        return fallback


def get_email_settings(user_id: str) -> Dict[str, Any]:
    result = _defaults()
    try:
        doc = db.collection("users").document(user_id).get()
        if doc.exists:
            stored = doc.to_dict().get("email_settings") or {}
            result.update({k: v for k, v in stored.items() if k in result})
    except Exception as e:
        print(f"[thread_store] get_email_settings failed: {e}")
    result["window_days"] = _clamp(result["window_days"], _WINDOW_MIN, _WINDOW_MAX,
                                   settings.EMAIL_SCAN_WINDOW_DAYS)
    result["followup_days"] = _clamp(result["followup_days"], _FOLLOWUP_MIN, _FOLLOWUP_MAX,
                                     settings.EMAIL_TRACKING_FOLLOWUP_DAYS)
    result["digest_email_enabled"] = bool(result["digest_email_enabled"])
    result["locale"] = result["locale"] if result["locale"] in ("es", "en") else "es"
    return result


def update_email_settings(user_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
    current = get_email_settings(user_id)
    if "window_days" in updates:
        current["window_days"] = _clamp(updates["window_days"], _WINDOW_MIN, _WINDOW_MAX,
                                        current["window_days"])
    if "followup_days" in updates:
        current["followup_days"] = _clamp(updates["followup_days"], _FOLLOWUP_MIN, _FOLLOWUP_MAX,
                                          current["followup_days"])
    if "digest_email_enabled" in updates:
        current["digest_email_enabled"] = bool(updates["digest_email_enabled"])
    if updates.get("locale") in ("es", "en"):
        current["locale"] = updates["locale"]
    db.collection("users").document(user_id).set({"email_settings": current}, merge=True)
    return current


def get_scan_meta(user_id: str) -> Dict[str, Any]:
    try:
        doc = db.collection("users").document(user_id).get()
        if doc.exists:
            return doc.to_dict().get("email_scan") or {}
    except Exception as e:
        print(f"[thread_store] get_scan_meta failed: {e}")
    return {}


def update_scan_meta(user_id: str, meta: Dict[str, Any]) -> None:
    db.collection("users").document(user_id).set({"email_scan": meta}, merge=True)
