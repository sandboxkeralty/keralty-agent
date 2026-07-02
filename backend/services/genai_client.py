import os
from google import genai
from config import settings


def get_genai_client() -> genai.Client:
    if os.getenv("GOOGLE_GENAI_USE_VERTEXAI") == "1":
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
