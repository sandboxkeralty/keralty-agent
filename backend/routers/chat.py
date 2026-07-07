import json
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Request as FastAPIRequest
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional
from google.genai import types
from agents.runner import runner
from services.firestore import FirestoreService
from models.schemas import SessionInDB, MessageInDB

router = APIRouter(prefix="/api/chat", tags=["chat"])

class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = "default-session"
    user_id: Optional[str] = "default-user"
    attached_context: Optional[str] = None  # text content of an attached Drive document

@router.post("")
async def chat_endpoint(body: ChatRequest, http_request: FastAPIRequest):
    user = getattr(http_request.state, "user", {})
    user_id = user.get("email") or user.get("uid") or body.user_id

    async def sse_generator():
        try:
            try:
                creds_dict = FirestoreService.get_user_credentials(user_id)
            except Exception as fs_err:
                print(f"[chat] Firestore unavailable: {fs_err}", flush=True)
                creds_dict = None

            try:
                session = await runner.session_service.get_session(
                    app_name="agents",
                    session_id=body.session_id,
                    user_id=user_id,
                )
                if session is None:
                    init_state = {"user_id": user_id}
                    if creds_dict:
                        init_state["google_credentials"] = creds_dict
                    await runner.session_service.create_session(
                        app_name="agents",
                        user_id=user_id,
                        session_id=body.session_id,
                        state=init_state,
                    )
                    # Persist session metadata to Firestore for history page
                    try:
                        now = datetime.now(timezone.utc)
                        FirestoreService.create_session(SessionInDB(
                            session_id=body.session_id,
                            user_id=user_id,
                            title=body.message[:80],
                            created_at=now,
                            updated_at=now,
                        ))
                    except Exception:
                        pass
                elif creds_dict:
                    session.state["google_credentials"] = creds_dict
                    session.state["user_id"] = user_id

                # Inject attached document context into session state
                if body.attached_context and session:
                    existing = session.state.get("attached_documents", [])
                    existing.append(body.attached_context[:8000])  # cap per-doc size
                    session.state["attached_documents"] = existing
            except Exception as e:
                print(f"Session error: {e}")

            # Persist user message
            try:
                FirestoreService.add_message(MessageInDB(
                    message_id=str(uuid.uuid4()),
                    session_id=body.session_id,
                    role="user",
                    content=body.message,
                    timestamp=datetime.now(timezone.utc),
                ))
            except Exception:
                pass

            # The attached document's text must be part of the actual message sent
            # to the model — session.state["attached_documents"] above is bookkeeping
            # only, nothing reads it back out, so without this the model never sees
            # what the user attached.
            message_parts = []
            if body.attached_context:
                message_parts.append(types.Part.from_text(
                    text=f"[Documento adjunto]\n{body.attached_context[:8000]}"
                ))
            message_parts.append(types.Part.from_text(text=body.message))

            full_response = ""
            async for event in runner.run_async(
                new_message=types.Content(role="user", parts=message_parts),
                session_id=body.session_id,
                user_id=user_id,
            ):
                if getattr(event, "content", None) is not None:
                    text = ""
                    if isinstance(event.content, str):
                        text = event.content
                    elif hasattr(event.content, "text"):
                        text = event.content.text
                    elif hasattr(event.content, "parts"):
                        for p in event.content.parts:
                            if p.text is not None:
                                text += p.text

                    if text:
                        full_response += text
                        yield f"data: {json.dumps({'type': 'content', 'text': text})}\n\n"

                if event.is_final_response():
                    yield f"data: {json.dumps({'type': 'final'})}\n\n"

            # Persist agent response
            if full_response:
                try:
                    FirestoreService.add_message(MessageInDB(
                        message_id=str(uuid.uuid4()),
                        session_id=body.session_id,
                        role="agent",
                        content=full_response,
                        timestamp=datetime.now(timezone.utc),
                    ))
                except Exception:
                    pass

        except Exception as e:
            print(f"Error in streaming: {e}")
            yield f"data: {json.dumps({'type': 'content', 'text': f'An error occurred: {str(e)}'})}\n\n"

    return StreamingResponse(sse_generator(), media_type="text/event-stream")
