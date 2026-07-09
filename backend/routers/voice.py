"""Voice pipeline using Gemini Live API.

Flow:
  Browser (mic) → PCM chunks → WebSocket → Gemini Live session → text transcript
  Frontend receives the transcript and submits it through the regular chat SSE pipeline.

WebSocket message protocol (all JSON):
  Browser → Backend:
    {"type": "audio_chunk", "data": "<base64 PCM 16kHz 16-bit mono>"}
    {"type": "end_turn"}          — user stopped speaking, close this audio turn
    {"type": "ping"}              — keepalive
  Backend → Browser:
    {"type": "status",     "message": "connected|ready|processing"}
    {"type": "transcript", "text": "...", "final": true|false}
    {"type": "turn_complete"}     — Gemini finished responding for this turn
    {"type": "error",      "message": "..."}
    {"type": "pong"}
"""

import asyncio
import base64
from typing import Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from google.genai import types

from config import settings
from services.genai_client import get_genai_client

router = APIRouter(prefix="/voice", tags=["voice"])

_SYSTEM_INSTRUCTION = (
    "Eres el asistente de voz de Keralty. "
    "Transcribe fielmente lo que escucha el usuario y responde de forma breve y profesional. "
    "Habla en español a menos que el usuario cambie de idioma."
)

_LIVE_AUDIO_MIME = "audio/pcm;rate=16000"


@router.websocket("/stream")
async def voice_stream(websocket: WebSocket):
    await websocket.accept()
    await _safe_send(websocket, {"type": "status", "message": "connected"})

    client = get_genai_client(force_vertex=True)
    # gemini-live-2.5-flash-native-audio is the only GA Live model on Vertex AI, and it only
    # supports AUDIO response modality (TEXT is rejected outright). This app only needs a
    # transcript of what the user said, not a spoken reply, so we request input audio
    # transcription instead of relying on response text — the model's audio reply is generated
    # but never read or forwarded to the browser.
    live_config = types.LiveConnectConfig(
        response_modalities=["AUDIO"],
        input_audio_transcription=types.AudioTranscriptionConfig(),
        system_instruction=_SYSTEM_INSTRUCTION,
        temperature=0.2,
    )

    try:
        async with client.aio.live.connect(
            model=settings.GEMINI_LIVE_MODEL,
            config=live_config,
        ) as session:
            await _safe_send(websocket, {"type": "status", "message": "ready"})
            await _run_session(websocket, session)

    except WebSocketDisconnect:
        pass
    except Exception as e:
        print(f"[voice] session error: {e}")
        await _safe_send(websocket, {"type": "error", "message": f"Voice session failed: {e}"})


async def _run_session(websocket: WebSocket, session) -> None:
    """Run concurrent browser-receive and Gemini-receive loops."""
    browser_task = asyncio.create_task(_recv_browser(websocket, session))
    gemini_task = asyncio.create_task(_recv_gemini(websocket, session))

    try:
        done, pending = await asyncio.wait(
            [browser_task, gemini_task],
            return_when=asyncio.FIRST_EXCEPTION,
        )
        for task in pending:
            task.cancel()
        # Re-raise any exception from completed tasks
        for task in done:
            if not task.cancelled():
                task.result()
    except (WebSocketDisconnect, asyncio.CancelledError):
        pass


async def _recv_browser(websocket: WebSocket, session) -> None:
    """Forward browser audio chunks to the Gemini Live session."""
    while True:
        try:
            msg = await websocket.receive_json()
        except Exception:
            raise WebSocketDisconnect()

        msg_type = msg.get("type")

        if msg_type == "audio_chunk":
            raw = base64.b64decode(msg["data"])
            await session.send_realtime_input(
                audio=types.Blob(data=raw, mime_type=_LIVE_AUDIO_MIME)
            )

        elif msg_type == "end_turn":
            # Signal end of this audio turn to Gemini
            await session.send_realtime_input(audio_stream_end=True)

        elif msg_type == "ping":
            await _safe_send(websocket, {"type": "pong"})


async def _recv_gemini(websocket: WebSocket, session) -> None:
    """Forward the input-audio transcript (what the user said) back to the browser.

    message.text would be the model's own spoken reply text, which doesn't exist here since
    response_modalities is AUDIO — the transcript of the user's speech comes from
    server_content.input_transcription instead.
    """
    async for message in session.receive():
        sc = message.server_content
        transcription = sc.input_transcription if sc else None

        if transcription and transcription.text:
            await _safe_send(websocket, {
                "type": "transcript",
                "text": transcription.text,
                "final": bool(transcription.finished),
            })

        if sc and sc.turn_complete:
            await _safe_send(websocket, {"type": "turn_complete"})


async def _safe_send(websocket: WebSocket, data: dict) -> None:
    try:
        await websocket.send_json(data)
    except Exception:
        pass
