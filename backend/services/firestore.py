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
