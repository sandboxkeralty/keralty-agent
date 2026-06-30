import json
from fastapi import APIRouter, Request as FastAPIRequest
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional
from google.genai import types
from agents.runner import runner
from services.firestore import FirestoreService

router = APIRouter(prefix="/api/chat", tags=["chat"])

class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = "default-session"
    user_id: Optional[str] = "default-user"

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
                    await runner.session_service.create_session(
                        app_name="agents",
                        user_id=user_id,
                        session_id=body.session_id,
                        state={"google_credentials": creds_dict} if creds_dict else {},
                    )
                elif creds_dict:
                    session.state["google_credentials"] = creds_dict
            except Exception as e:
                print(f"Session error: {e}")

            async for event in runner.run_async(
                new_message=types.Content(role="user", parts=[types.Part.from_text(text=body.message)]),
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
                        yield f"data: {json.dumps({'type': 'content', 'text': text})}\n\n"

                if event.is_final_response():
                    yield f"data: {json.dumps({'type': 'final'})}\n\n"
        except Exception as e:
            print(f"Error in streaming: {e}")
            yield f"data: {json.dumps({'type': 'content', 'text': f'An error occurred: {str(e)}'})}\n\n"

    return StreamingResponse(sse_generator(), media_type="text/event-stream")
