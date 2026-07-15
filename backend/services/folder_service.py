"""Per-user chat folders (ChatGPT-Projects style organization).

Firestore collection `chat_folders`, ownership-checked like writing_styles /
signatures. Sessions reference a folder via `sessions.folder_id` (nullable —
null means "Sin carpeta"). Grouping is done client-side; the only server query
by folder is `sessions_in_folder` (two equality filters — no composite index
needed: Firestore serves multi-equality via zig-zag merge without one).
"""

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from services.firestore import db

_COLLECTION = "chat_folders"

MAX_NAME_CHARS = 40


def list_user_folders(user_id: str) -> List[Dict[str, Any]]:
    docs = db.collection(_COLLECTION).where("user_id", "==", user_id).stream()
    folders = [d.to_dict() for d in docs]
    folders.sort(key=lambda f: (f.get("name") or "").lower())
    return folders


def get_folder(folder_id: str, user_id: str) -> Optional[Dict[str, Any]]:
    try:
        doc = db.collection(_COLLECTION).document(folder_id).get()
        if not doc.exists:
            return None
        data = doc.to_dict()
        if data.get("user_id") != user_id:
            return None
        return data
    except Exception as e:
        print(f"[folder_service] get_folder failed: {e}")
        return None


def create_folder(user_id: str, name: str) -> Dict[str, Any]:
    now = datetime.now(timezone.utc).isoformat()
    folder = {
        "folder_id": str(uuid.uuid4()),
        "user_id": user_id,
        "name": name.strip()[:MAX_NAME_CHARS],
        "created_at": now,
        "updated_at": now,
    }
    db.collection(_COLLECTION).document(folder["folder_id"]).set(folder)
    return folder


def rename_folder(folder_id: str, user_id: str, name: str) -> Optional[Dict[str, Any]]:
    if get_folder(folder_id, user_id) is None:
        return None
    ref = db.collection(_COLLECTION).document(folder_id)
    ref.update({
        "name": name.strip()[:MAX_NAME_CHARS],
        "updated_at": datetime.now(timezone.utc).isoformat(),
    })
    return ref.get().to_dict()


def delete_folder(folder_id: str, user_id: str) -> bool:
    if get_folder(folder_id, user_id) is None:
        return False
    db.collection(_COLLECTION).document(folder_id).delete()
    return True


def sessions_in_folder(user_id: str, folder_id: str) -> List[str]:
    docs = (
        db.collection("sessions")
        .where("user_id", "==", user_id)
        .where("folder_id", "==", folder_id)
        .stream()
    )
    return [d.id for d in docs]
