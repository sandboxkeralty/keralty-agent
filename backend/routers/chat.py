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

                # Keep only the current turn's attachment in session state, capped
                # at 8000 chars. This dict is serialized to the adk_sessions Firestore
                # doc on every event; an unbounded append would walk toward the 1 MB
                # document limit and eventually break state persistence silently. The
                # attachment is also injected into the message parts below (the path
                # the model actually reads), so session state doesn't need history.
                if body.attached_context and session:
                    session.state["attached_documents"] = [body.attached_context[:8000]]
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
            last_status = None
            async for event in runner.run_async(
                new_message=types.Content(role="user", parts=message_parts),
                session_id=body.session_id,
                user_id=user_id,
            ):
                # Surface which agent/tool is working so the frontend can show a
                # meaningful "Consultando la base de conocimiento…" style label
                # instead of a bare blinking cursor. Deduped: only emitted when
                # the (agent, tool) pair changes.
                author = getattr(event, "author", None)
                tool = None
                try:
                    calls = event.get_function_calls()
                    if calls:
                        tool = calls[0].name
                except Exception:
                    pass
                if author != "user" and (author or tool) and (author, tool) != last_status:
                    last_status = (author, tool)
                    yield f"data: {json.dumps({'type': 'status', 'agent': author, 'tool': tool})}\n\n"

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
            # Log the real detail server-side, but never stream raw exception text
            # (Firestore/Google API errors, internal IDs, stack details) to the
            # user — that violates the "no internal details" guardrail. The frontend
            # renders a localized message for the `error` event type.
            print(f"Error in streaming: {type(e).__name__}: {e}", flush=True)
            yield f"data: {json.dumps({'type': 'error'})}\n\n"

    return StreamingResponse(sse_generator(), media_type="text/event-stream")
