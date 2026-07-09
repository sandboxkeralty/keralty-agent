import os
from google import genai
from config import settings


def get_genai_client(force_vertex: bool = False) -> genai.Client:
    # force_vertex: the voice pipeline (Live API) must stay on Vertex even when
    # the rest of the app runs on an AI Studio API key —
    # gemini-live-2.5-flash-native-audio is the Vertex catalog's GA Live model,
    # and the direct Gemini API's Live catalog differs (see routers/voice.py).
    if force_vertex or os.getenv("GOOGLE_GENAI_USE_VERTEXAI") == "1":
        return genai.Client(
            vertexai=True,
            project=settings.GOOGLE_CLOUD_PROJECT,
            location=settings.GOOGLE_CLOUD_REGION,
        )
    if settings.GOOGLE_API_KEY:
        return genai.Client(api_key=settings.GOOGLE_API_KEY)
    # Fall back to Vertex AI ADC
    return genai.Client(
        vertexai=True,
        project=settings.GOOGLE_CLOUD_PROJECT,
        location=settings.GOOGLE_CLOUD_REGION,
    )
