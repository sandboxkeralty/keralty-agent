import json
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional
from google.genai import types
from agents.runner import runner
from config import settings

router = APIRouter(prefix="/api/chat", tags=["chat"])

class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = "default-session"
    user_id: Optional[str] = "default-user"

@router.post("")
async def chat_endpoint(request: ChatRequest):
    async def sse_generator():
        try:
            try:
                session = await runner.session_service.get_session(
                    app_name="agents", 
                    session_id=request.session_id,
                    user_id=request.user_id
                )
                if session is None:
                    await runner.session_service.create_session(
                        app_name="agents", 
                        user_id=request.user_id, 
                        session_id=request.session_id
                    )
            except Exception as e:
                print(f"Session error: {e}")
                
            async for event in runner.run_async(
                new_message=types.Content(role="user", parts=[types.Part.from_text(text=request.message)]),
                session_id=request.session_id,
                user_id=request.user_id
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
