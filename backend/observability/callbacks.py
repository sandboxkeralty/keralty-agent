from google_adk.callbacks import BaseCallbackHandler
from .logging import logger
from services.firestore import FirestoreService
from models.schemas import AuditEvent
import hashlib
from datetime import datetime, timezone
import uuid

class AuditCallbackHandler(BaseCallbackHandler):
    def __init__(self, user_email: str):
        # We hash the email to avoid PII in logs
        self.user_email_hash = hashlib.sha256(user_email.encode('utf-8')).hexdigest()

    def on_tool_start(self, tool, *args, **kwargs):
        # Audit critical tools that modify state or send data
        if tool.name in ["approval_create", "send_email", "write_docs", "write_slides"]:
            logger.info(f"High-privilege tool {tool.name} started by {self.user_email_hash}")
            event = AuditEvent(
                event_id=str(uuid.uuid4()),
                user_email_hash=self.user_email_hash,
                action=tool.name,
                resource_type="tool",
                resource_id=tool.name,
                timestamp=datetime.now(timezone.utc),
                metadata={"args": str(args), "kwargs": str(kwargs)}
            )
            FirestoreService.log_audit_event(event)

    def on_tool_end(self, tool, result, *args, **kwargs):
        if tool.name in ["approval_create", "send_email", "write_docs", "write_slides"]:
            logger.info(f"High-privilege tool {tool.name} finished. Result: {result}")
