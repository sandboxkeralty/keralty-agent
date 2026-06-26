from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import json

router = APIRouter(prefix="/voice", tags=["voice"])

@router.websocket("/stream")
async def voice_stream(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_text()
            # Mock Gemini Live API integration
            # In a real scenario, bytes would be sent/received and piped to the LLM
            await websocket.send_text(json.dumps({"type": "status", "message": "listening"}))
    except WebSocketDisconnect:
        pass
    except Exception as e:
        print(f"Voice WebSocket error: {e}")
