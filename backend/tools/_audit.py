import uuid
import hashlib
from datetime import datetime, timezone
from models.schemas import AuditEvent
from services.firestore import FirestoreService


def _audit(tool_context, action: str, resource_type: str, resource_id: str):
    try:
        user_id = getattr(getattr(tool_context, "session", None), "user_id", None) or ""
        FirestoreService.log_audit_event(AuditEvent(
            event_id=str(uuid.uuid4()),
            user_email_hash=hashlib.sha256(user_id.encode()).hexdigest(),
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            timestamp=datetime.now(timezone.utc),
        ))
    except Exception:
        pass
