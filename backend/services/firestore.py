from google.cloud import firestore
from config import settings
from models.schemas import UserInDB, SessionInDB, MessageInDB, AuditEvent
from typing import Optional, List
from datetime import datetime

db = firestore.Client(project=settings.GOOGLE_CLOUD_PROJECT, database=settings.FIRESTORE_DATABASE)

class FirestoreService:
    @staticmethod
    def get_user(user_id: str) -> Optional[UserInDB]:
        doc = db.collection("users").document(user_id).get()
        if doc.exists:
            return UserInDB(**doc.to_dict())
        return None

    @staticmethod
    def create_user(user: UserInDB):
        # Using model_dump() instead of dict() for Pydantic v2
        db.collection("users").document(user.user_id).set(user.model_dump())

    @staticmethod
    def create_session(session: SessionInDB):
        db.collection("sessions").document(session.session_id).set(session.model_dump())

    @staticmethod
    def get_session(session_id: str) -> Optional[SessionInDB]:
        doc = db.collection("sessions").document(session_id).get()
        if doc.exists:
            return SessionInDB(**doc.to_dict())
        return None

    @staticmethod
    def get_sessions_by_user(user_id: str) -> List[SessionInDB]:
        docs = db.collection("sessions").where("user_id", "==", user_id).order_by("updated_at", direction=firestore.Query.DESCENDING).stream()
        return [SessionInDB(**doc.to_dict()) for doc in docs]

    @staticmethod
    def add_message(message: MessageInDB):
        db.collection("messages").document(message.message_id).set(message.model_dump())
        
        # Update session updated_at
        db.collection("sessions").document(message.session_id).update({
            "updated_at": message.timestamp
        })

    @staticmethod
    def get_messages(session_id: str) -> List[MessageInDB]:
        docs = db.collection("messages").where("session_id", "==", session_id).order_by("timestamp").stream()
        return [MessageInDB(**doc.to_dict()) for doc in docs]

    @staticmethod
    def log_audit_event(event: AuditEvent):
        db.collection("audit_events").document(event.event_id).set(event.model_dump())

    @staticmethod
    def create_task(task_id: str, payload: dict):
        db.collection("tasks").document(task_id).set(payload)

    @staticmethod
    def get_task(task_id: str) -> Optional[dict]:
        doc = db.collection("tasks").document(task_id).get()
        return doc.to_dict() if doc.exists else None

    @staticmethod
    def update_task(task_id: str, updates: dict):
        db.collection("tasks").document(task_id).update(updates)

    @staticmethod
    def get_pending_tasks(user_id: str) -> List[dict]:
        docs = db.collection("tasks").where("user_id", "==", user_id).where("status", "==", "pending").stream()
        return [{"task_id": doc.id, **doc.to_dict()} for doc in docs]

    @staticmethod
    def find_approved_task(user_id: str, document_id: str) -> Optional[dict]:
        """Returns an approved, user-owned, not-yet-consumed task for the given
        resource (document_id / draft_id / spreadsheet_id), or None.

        This is the server-side gate behind the HITL approval flow: destructive
        tools call it before executing so approval can never be satisfied by the
        agent merely reading the literal text "[APROBADO] task_id=..." (which a
        prompt-injected attachment could emit). Ownership + approved-status are
        enforced in code, not in the prompt.
        """
        docs = (
            db.collection("tasks")
            .where("user_id", "==", user_id)
            .where("document_id", "==", document_id)
            .where("status", "==", "approved")
            .stream()
        )
        for doc in docs:
            return {"task_id": doc.id, **doc.to_dict()}
        return None

    @staticmethod
    def consume_task(task_id: str) -> None:
        """Marks an approved task as consumed so a single approval can authorize
        exactly one execution (prevents replay of the same [APROBADO] message)."""
        from datetime import timezone
        db.collection("tasks").document(task_id).update({
            "status": "consumed",
            "consumed_at": datetime.now(timezone.utc),
        })

    @staticmethod
    def store_user_credentials(user_id: str, user_info: dict, creds_dict: dict):
        """Full profile write — only used at login (routers/auth.py), where
        user_info is populated. Never call this from a token-refresh path with
        an empty user_info, or it will null out email/name/picture."""
        from datetime import timezone
        db.collection("users").document(user_id).set({
            "user_id": user_id,
            "email": user_info.get("email"),
            "name": user_info.get("name"),
            "picture": user_info.get("picture"),
            "google_credentials": creds_dict,
            "updated_at": datetime.now(timezone.utc),
        }, merge=True)

    @staticmethod
    def update_credentials(user_id: str, creds_dict: dict):
        """Persists refreshed OAuth credentials WITHOUT touching profile fields.

        The token-refresh hot path (tools/_auth.py, routers/email.py,
        routers/documents.py) uses this instead of store_user_credentials — the
        latter would write email/name/picture as null (merge=True does not skip
        None), silently wiping the user's profile on every routine refresh.
        """
        from datetime import timezone
        db.collection("users").document(user_id).set({
            "google_credentials": creds_dict,
            "updated_at": datetime.now(timezone.utc),
        }, merge=True)

    @staticmethod
    def get_user_credentials(user_id: str) -> Optional[dict]:
        doc = db.collection("users").document(user_id).get()
        if doc.exists:
            return doc.to_dict().get("google_credentials")
        return None

    @staticmethod
    def list_users(limit: int = 100) -> List[dict]:
        docs = db.collection("users").limit(limit).stream()
        result = []
        for doc in docs:
            d = doc.to_dict()
            d.pop("google_credentials", None)  # never expose tokens
            result.append(d)
        return result

    @staticmethod
    def get_metrics() -> dict:
        session_count = sum(1 for _ in db.collection("sessions").stream())
        message_count = sum(1 for _ in db.collection("messages").stream())
        audit_count   = sum(1 for _ in db.collection("audit_events").stream())
        user_count    = sum(1 for _ in db.collection("users").stream())
        return {
            "users": user_count,
            "sessions": session_count,
            "messages": message_count,
            "audit_events": audit_count,
        }

    @staticmethod
    def get_audit_logs(limit: int = 50) -> List[dict]:
        docs = (
            db.collection("audit_events")
            .order_by("timestamp", direction=firestore.Query.DESCENDING)
            .limit(limit)
            .stream()
        )
        return [doc.to_dict() for doc in docs]
