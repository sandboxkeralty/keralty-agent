"""Firestore-backed ADK session service.

Persists session state (OAuth credentials, user_id) to Firestore so it
survives Cloud Run cold starts. ADK events (the in-request conversation
turn buffer) are kept in-memory per-session; they are not needed across
restarts because message history is persisted separately in routers/chat.py.
"""

import copy
import time
import uuid
from typing import Any, Optional

from google.adk.sessions import BaseSessionService, InMemorySessionService, Session
from google.adk.sessions.in_memory_session_service import ListSessionsResponse
from google.adk.events import Event
from google.cloud import firestore

from config import settings

_COLLECTION = "adk_sessions"


class FirestoreSessionService(BaseSessionService):
    """ADK session service backed by Firestore for state persistence.

    Session state (credentials, user_id) is written to Firestore on every
    state change. Events are cached in-memory for the lifetime of the process.
    """

    def __init__(self):
        self._db = firestore.Client(
            project=settings.GOOGLE_CLOUD_PROJECT,
            database=settings.FIRESTORE_DATABASE,
        )
        # In-memory event store: {app_name: {user_id: {session_id: Session}}}
        self._sessions: dict[str, dict[str, dict[str, Session]]] = {}

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _doc_ref(self, app_name: str, session_id: str):
        return self._db.collection(_COLLECTION).document(f"{app_name}_{session_id}")

    def _write_state(self, session: Session) -> None:
        try:
            self._doc_ref(session.app_name, session.id).set(
                {
                    "app_name": session.app_name,
                    "user_id": session.user_id,
                    "session_id": session.id,
                    "state": dict(session.state),
                    "last_update_time": session.last_update_time,
                },
                merge=True,
            )
        except Exception as e:
            print(f"[FirestoreSessionService] state write failed: {e}")

    def _load_from_firestore(self, app_name: str, session_id: str) -> Optional[Session]:
        try:
            doc = self._doc_ref(app_name, session_id).get()
            if not doc.exists:
                return None
            data = doc.to_dict()
            session = Session(
                app_name=data["app_name"],
                user_id=data["user_id"],
                id=data["session_id"],
                state=data.get("state", {}),
                events=[],
                last_update_time=data.get("last_update_time", 0.0),
            )
            return session
        except Exception as e:
            print(f"[FirestoreSessionService] load failed: {e}")
            return None

    def _get_or_restore(self, app_name: str, user_id: str, session_id: str) -> Optional[Session]:
        """Return in-memory session, or restore from Firestore if not found."""
        mem = (
            self._sessions.get(app_name, {})
            .get(user_id, {})
            .get(session_id)
        )
        if mem is not None:
            return mem
        restored = self._load_from_firestore(app_name, session_id)
        if restored:
            self._sessions.setdefault(app_name, {}).setdefault(user_id, {})[session_id] = restored
        return restored

    # ------------------------------------------------------------------
    # BaseSessionService interface
    # ------------------------------------------------------------------

    async def create_session(
        self,
        *,
        app_name: str,
        user_id: str,
        state: Optional[dict[str, Any]] = None,
        session_id: Optional[str] = None,
    ) -> Session:
        session_id = (session_id or str(uuid.uuid4())).strip()
        session = Session(
            app_name=app_name,
            user_id=user_id,
            id=session_id,
            state=state or {},
            last_update_time=time.time(),
        )
        self._sessions.setdefault(app_name, {}).setdefault(user_id, {})[session_id] = session
        self._write_state(session)
        return copy.deepcopy(session)

    async def get_session(
        self,
        *,
        app_name: str,
        user_id: str,
        session_id: str,
        config=None,
    ) -> Optional[Session]:
        session = self._get_or_restore(app_name, user_id, session_id)
        if session is None:
            return None
        copied = copy.deepcopy(session)
        if config:
            if getattr(config, "num_recent_events", None):
                copied.events = copied.events[-config.num_recent_events:]
            if getattr(config, "after_timestamp", None):
                i = len(copied.events) - 1
                while i >= 0 and copied.events[i].timestamp >= config.after_timestamp:
                    i -= 1
                copied.events = copied.events[i + 1:] if i >= 0 else copied.events
        return copied

    async def list_sessions(
        self, *, app_name: str, user_id: Optional[str] = None
    ) -> ListSessionsResponse:
        if app_name not in self._sessions:
            return ListSessionsResponse()
        sessions = []
        users = [user_id] if user_id else list(self._sessions[app_name].keys())
        for uid in users:
            for s in self._sessions[app_name].get(uid, {}).values():
                c = copy.deepcopy(s)
                c.events = []
                sessions.append(c)
        return ListSessionsResponse(sessions=sessions)

    async def delete_session(
        self, *, app_name: str, user_id: str, session_id: str
    ) -> None:
        self._sessions.get(app_name, {}).get(user_id, {}).pop(session_id, None)
        try:
            self._doc_ref(app_name, session_id).delete()
        except Exception as e:
            print(f"[FirestoreSessionService] delete failed: {e}")

    async def append_event(self, session: Session, event: Event) -> Event:
        event = await super().append_event(session=session, event=event)
        if event.partial:
            return event

        stored = (
            self._sessions.get(session.app_name, {})
            .get(session.user_id, {})
            .get(session.id)
        )
        if stored is not None:
            stored.events.append(event)
            stored.last_update_time = event.timestamp
            if event.actions and event.actions.state_delta:
                stored.state.update(
                    {k: v for k, v in event.actions.state_delta.items()
                     if not k.startswith("_")}
                )
        self._write_state(session)
        return event
