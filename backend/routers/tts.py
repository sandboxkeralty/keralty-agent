"""On-demand text-to-speech using Gemini's native audio generation.

Replaces the frontend's browser speechSynthesis-based read-aloud (inconsistent
voice quality, wrong accent for non-English locales) with server-generated
audio. Gemini's TTS models are multilingual and detect the input language from
the text itself — the same voice persona pronounces Spanish and English
correctly, so there's no need to select a "Spanish voice" specifically.
"""

import io
import re
import wave

from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel
from google.genai import types

from config import settings
from services.genai_client import get_genai_client

router = APIRouter(prefix="/api/tts", tags=["tts"])


class TTSRequest(BaseModel):
    text: str
    locale: str = "es"  # informational only — Gemini auto-detects language from text


@router.post("")
async def generate_tts(req: TTSRequest) -> Response:
    if not req.text.strip():
        raise HTTPException(status_code=400, detail="text must not be empty")

    client = get_genai_client()
    config = types.GenerateContentConfig(
        response_modalities=["AUDIO"],
        speech_config=types.SpeechConfig(
            voice_config=types.VoiceConfig(
                prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=settings.GEMINI_TTS_VOICE)
            ),
        ),
    )

    try:
        response = await client.aio.models.generate_content(
            model=settings.GEMINI_TTS_MODEL,
            contents=req.text,
            config=config,
        )
        parts = response.candidates[0].content.parts
        audio_part = next(p for p in parts if p.inline_data)
        pcm_bytes = audio_part.inline_data.data
        mime = audio_part.inline_data.mime_type or ""
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"TTS generation failed: {e}")

    rate_match = re.search(r"rate=(\d+)", mime)
    sample_rate = int(rate_match.group(1)) if rate_match else 24000

    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)  # 16-bit PCM
        wf.setframerate(sample_rate)
        wf.writeframes(pcm_bytes)

    return Response(content=buf.getvalue(), media_type="audio/wav")
