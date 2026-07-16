import traceback
import uuid
from typing import Optional

from google.adk.tools import ToolContext
from config import settings
from services import brand

# Tried in order after the configured model; ends at the model probed working
# on keraltysandbox (July 2026: imagen-4.0-* and 3.0-002 return 404 there, but
# the chain makes a future IMAGEN_MODEL bump a settings-only change).
_IMAGEN_FALLBACKS = [
    "imagen-4.0-generate-001",
    "imagen-3.0-generate-002",
    "imagen-3.0-generate-001",
]
_working_model: Optional[str] = None  # cached for the process lifetime


def _enrich_prompt(subject: str) -> str:
    """Art-directs a short subject description into a full image prompt.

    Adds composition, lighting, color mood and professional-style directives —
    the difference between "plain gradient clipart" and a usable corporate
    visual. Degrades to the raw subject on any failure; never blocks generation.
    """
    try:
        from google.genai import types
        from services.genai_client import get_genai_client

        client = get_genai_client()
        response = client.models.generate_content(
            model=settings.GEMINI_FLASH_MODEL,
            contents=(
                "Rewrite the following subject as ONE single English image-generation "
                "prompt for premium corporate healthcare imagery. Include: the subject, "
                "a concrete composition (camera angle or framing), lighting (soft, "
                "natural or studio), the brand color mood and photography premises "
                "below, and a style (professional editorial photography OR clean "
                "modern flat illustration — pick whichever suits the subject). "
                f"{brand.IMAGE_STYLE_DIRECTIVE} "
                "End the prompt with: 'no text, no logos, no watermarks, no "
                "identifiable faces'. Output ONLY the prompt, nothing else.\n\n"
                f"Subject: {subject}"
            ),
            config=types.GenerateContentConfig(
                temperature=0.4,
                max_output_tokens=250,
                # 2.5-Flash burns the budget on invisible reasoning without this
                # (see services/email/triage_service.py).
                thinking_config=types.ThinkingConfig(thinking_budget=0),
            ),
        )
        enriched = (response.text or "").strip()
        return enriched if enriched else subject
    except Exception as e:
        print(f"[image_generate] prompt enrichment failed, using raw prompt: {e}", flush=True)
        return subject


def _generate_openai_image(enriched_prompt: str) -> bytes:
    """OpenAI images API path — used when the conversation's selected chat
    model is an OpenAI one (product decision). Raises on any failure; the
    caller falls back to the Imagen path so an OpenAI outage never costs the
    user their image."""
    import base64
    from openai import OpenAI

    client = OpenAI(api_key=settings.OPENAI_API_KEY)
    result = client.images.generate(
        model=settings.OPENAI_IMAGE_MODEL,
        prompt=enriched_prompt,
        size="1536x1024",  # closest available to the 16:9 house format
        n=1,
    )
    b64 = result.data[0].b64_json
    if not b64:
        raise RuntimeError("OpenAI images returned no b64_json payload")
    return base64.b64decode(b64)


async def image_generate(prompt: str, tool_context: ToolContext = None) -> dict:
    """Generates a 16:9 corporate image and uploads it to GCS.

    Engine: Vertex AI Imagen by default; the OpenAI images API when the
    conversation's selected chat model is an OpenAI one (read from session
    state — never a tool argument the model could get wrong).

    Args:
        prompt: Concise description of the image SUBJECT (one sentence is
            enough — art direction such as composition, lighting and style is
            added automatically).
    """
    global _working_model
    try:
        import base64
        import google.auth
        from google.auth.transport.requests import AuthorizedSession
        from google.cloud import storage

        # REST :predict with explicit ADC OAuth — NOT the vertexai SDK. With
        # GOOGLE_API_KEY in the environment, the SDK's preview vision-models
        # path silently uses API-key transport ("project 0") and 403s on every
        # publisher model even when vertexai.init receives explicit credentials
        # (the embeddings path honors them; this one doesn't). The REST call
        # was verified working on this project.
        adc, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
        session = AuthorizedSession(adc)

        enriched = _enrich_prompt(prompt)

        image_bytes = None
        used_model = None

        # OpenAI-selected conversations generate with OpenAI images; any
        # failure falls through to the Imagen path below (never a dead turn).
        state = getattr(tool_context, "state", {}) if tool_context else {}
        if state.get("model_provider") == "openai" and settings.OPENAI_API_KEY:
            try:
                image_bytes = _generate_openai_image(enriched)
                used_model = settings.OPENAI_IMAGE_MODEL
            except Exception as oe:
                traceback.print_exc()
                print(f"[image_generate] OPENAI IMAGE FAILED: {oe} — falling back to Imagen",
                      flush=True)

        candidates = [settings.IMAGEN_MODEL] + [
            m for m in _IMAGEN_FALLBACKS if m != settings.IMAGEN_MODEL
        ]
        if _working_model and _working_model in candidates:
            candidates.remove(_working_model)
            candidates.insert(0, _working_model)

        last_err = None
        base = (f"https://{settings.GOOGLE_CLOUD_REGION}-aiplatform.googleapis.com/v1/"
                f"projects/{settings.GOOGLE_CLOUD_PROJECT}/locations/{settings.GOOGLE_CLOUD_REGION}"
                f"/publishers/google/models")
        for m in candidates if image_bytes is None else []:
            resp = session.post(
                f"{base}/{m}:predict",
                json={"instances": [{"prompt": enriched}],
                      "parameters": {"sampleCount": 1,
                                     "aspectRatio": settings.IMAGEN_ASPECT_RATIO}},
                timeout=120,
            )
            if resp.status_code == 200:
                preds = resp.json().get("predictions") or []
                if not preds:
                    last_err = "empty predictions (possibly safety-filtered)"
                    continue
                image_bytes = base64.b64decode(preds[0]["bytesBase64Encoded"])
                used_model = m
                _working_model = m
                break
            last_err = f"HTTP {resp.status_code}: {resp.text[:160]}"
            if resp.status_code in (403, 404):
                print(f"[image_generate] model {m} unavailable, trying next: {last_err}",
                      flush=True)
                continue
            raise RuntimeError(last_err)

        if image_bytes is None:
            raise RuntimeError(f"ALL MODELS FAILED — last error: {last_err}")

        blob_name = f"images/{uuid.uuid4()}.png"
        client = storage.Client(project=settings.GOOGLE_CLOUD_PROJECT)
        bucket = client.bucket(settings.GCS_BUCKET)
        blob = bucket.blob(blob_name)
        blob.upload_from_string(image_bytes, content_type="image/png")
        blob.make_public()

        return {
            "status": "success",
            "image_url": blob.public_url,
            "gcs_path": f"gs://{settings.GCS_BUCKET}/{blob_name}",
            "model": used_model,
            "enriched_prompt": enriched,
        }

    except Exception as e:
        # The placeholder fallback keeps the agent flow alive, but it has
        # masked real failures before — log loudly (see CLAUDE.md, Imagen).
        traceback.print_exc()
        print(f"[image_generate] FAILED: {type(e).__name__}: {e}", flush=True)
        return {"status": "error", "error": str(e),
                "image_url": "https://via.placeholder.com/1024x768?text=Image+Generation+Failed"}
