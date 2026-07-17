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

# Gemini-native image models (Nano Banana) — PRIMARY Gemini-path engine since
# 2026-07-17. Probed live on the backend's AI Studio key: both served, and
# unlike Imagen 3 they render in-image text correctly (the skill
# gemini-api-image-gen documents exactly these models; an HL7 infographic on
# Imagen 3 shipped with garbled labels). The Vertex Imagen :predict chain
# below stays as fallback (it's ADC-based, so it also survives an API-key
# removal).
_NANO_BANANA_MODELS = [
    "gemini-3.1-flash-image",
    "gemini-2.5-flash-image",
]


def _generate_gemini_api_image(enriched_prompt: str):
    """Nano Banana generation via the shared genai client.

    Returns (bytes, mime_type, model) or (None, None, None) — any failure
    falls through to the Imagen REST chain, never raises.
    """
    try:
        from google.genai import types
        from services.genai_client import get_genai_client

        client = get_genai_client()
        for m in _NANO_BANANA_MODELS:
            try:
                resp = client.models.generate_content(
                    model=m,
                    contents=enriched_prompt,
                    config=types.GenerateContentConfig(
                        response_modalities=["IMAGE"],
                        image_config=types.ImageConfig(
                            aspect_ratio=settings.IMAGEN_ASPECT_RATIO
                        ),
                    ),
                )
                for part in resp.candidates[0].content.parts:
                    inline = getattr(part, "inline_data", None)
                    if inline and inline.data:
                        mime = inline.mime_type or "image/png"
                        return inline.data, mime, m
                print(f"[image_generate] {m}: no image part in response", flush=True)
            except Exception as e:
                print(f"[image_generate] {m} failed, trying next: {e}", flush=True)
    except Exception as e:
        print(f"[image_generate] gemini-api image path unavailable: {e}", flush=True)
    return None, None, None


def _enrich_prompt(subject: str, provider: str = "google") -> str:
    """Art-directs a short subject description into a full image prompt.

    Adds composition, lighting, color mood and professional-style directives —
    the difference between "plain gradient clipart" and a usable corporate
    visual. Degrades to the raw subject on any failure; never blocks generation.
    """
    try:
        from google.genai import types
        from services.genai_client import get_genai_client
        from services import skill_registry

        skill_guidance = skill_registry.full_guidance_for_tool("image_generate", provider)
        source = "skill" if skill_guidance else "brand-fallback"
        print(f"[image_generate] art direction source: {source} (provider={provider})",
              flush=True)
        # Brand color mood always rides along; the skill (when present) adds
        # the per-use-case prompting craft on top of it.
        guidance = (
            f"{skill_guidance}\n\n{brand.IMAGE_STYLE_DIRECTIVE}"
            if skill_guidance
            else brand.IMAGE_STYLE_DIRECTIVE
        )

        client = get_genai_client()
        response = client.models.generate_content(
            model=settings.GEMINI_FLASH_MODEL,
            contents=(
                "Rewrite the following subject as ONE single English image-generation "
                "prompt for premium corporate healthcare imagery. Classify the use "
                "case (photo, infographic/diagram, logo, ad, mockup, illustration) "
                "and apply the matching guidance below: concrete composition (camera "
                "angle or framing), lighting, and style. This platform only GENERATES "
                "images (no editing) and accepts no API parameters — ignore any "
                "size/quality/n/input_fidelity recommendations and output ONLY the "
                "prompt text.\n\n"
                f"{guidance}\n\n"
                "The image backend renders ADULTS ONLY (its safety filter rejects "
                "any image containing minors): never mention children, kids, "
                "babies or minors in the prompt — for family subjects, describe "
                "adult family members or a composition without minors. "
                "Unless the subject is an infographic or diagram that explicitly "
                "needs labeled text, end the prompt with: 'adults only, no "
                "children, no text, no logos, no watermarks, no identifiable "
                "faces' (for infographics/diagrams use: 'no watermarks, no logos, "
                "no identifiable faces' and keep the requested labels). Output "
                "ONLY the prompt, nothing else.\n\n"
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

        # Provider decides both the generation path below AND which image
        # skill guides the enrichment (image-gen-pro is OpenAI-scoped,
        # gemini-api-image-gen covers the Gemini/Imagen path).
        state = getattr(tool_context, "state", {}) if tool_context else {}
        provider = state.get("model_provider") or "google"
        if provider == "openai" and not settings.OPENAI_API_KEY:
            provider = "google"

        enriched = _enrich_prompt(prompt, provider)

        image_bytes = None
        used_model = None

        # OpenAI-selected conversations generate with OpenAI images; any
        # failure falls through to the Imagen path below (never a dead turn).
        image_mime = "image/png"  # OpenAI and Imagen both return PNG

        if provider == "openai":
            try:
                image_bytes = _generate_openai_image(enriched)
                used_model = settings.OPENAI_IMAGE_MODEL
            except Exception as oe:
                traceback.print_exc()
                print(f"[image_generate] OPENAI IMAGE FAILED: {oe} — falling back to Imagen",
                      flush=True)

        # Gemini path (and any OpenAI failure): Nano Banana first — it renders
        # in-image text correctly; Imagen 3 (REST chain below) is the fallback.
        if image_bytes is None:
            nb_bytes, nb_mime, nb_model = _generate_gemini_api_image(enriched)
            if nb_bytes:
                image_bytes, image_mime, used_model = nb_bytes, nb_mime, nb_model

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
            # Imagen's RAI filter is nondeterministic on people subjects —
            # observed live: the same prompt alternates between an image and an
            # empty/filtered prediction. One retry per model recovers most of
            # these instead of falling through to the (dead, 404) fallbacks.
            for attempt in (1, 2):
                resp = session.post(
                    f"{base}/{m}:predict",
                    json={"instances": [{"prompt": enriched}],
                          "parameters": {"sampleCount": 1,
                                         "aspectRatio": settings.IMAGEN_ASPECT_RATIO,
                                         "includeRaiReason": True}},
                    timeout=120,
                )
                if resp.status_code != 200:
                    break
                preds = resp.json().get("predictions") or []
                img_b64 = preds[0].get("bytesBase64Encoded") if preds else None
                if img_b64:
                    image_bytes = base64.b64decode(img_b64)
                    used_model = m
                    _working_model = m
                    break
                reason = (preds[0].get("raiFilteredReason") if preds else None) \
                    or "no predictions returned"
                last_err = f"safety-filtered/empty ({reason})"
                print(f"[image_generate] model {m} attempt {attempt}: {last_err}",
                      flush=True)
            if image_bytes is not None:
                break
            if resp.status_code == 200:
                continue  # filtered twice — try next model
            last_err = f"HTTP {resp.status_code}: {resp.text[:160]}"
            if resp.status_code in (403, 404):
                print(f"[image_generate] model {m} unavailable, trying next: {last_err}",
                      flush=True)
                continue
            raise RuntimeError(last_err)

        if image_bytes is None:
            raise RuntimeError(f"ALL MODELS FAILED — last error: {last_err}")

        ext = "jpg" if image_mime == "image/jpeg" else "png"
        blob_name = f"images/{uuid.uuid4()}.{ext}"
        client = storage.Client(project=settings.GOOGLE_CLOUD_PROJECT)
        bucket = client.bucket(settings.GCS_BUCKET)
        blob = bucket.blob(blob_name)
        blob.upload_from_string(image_bytes, content_type=image_mime)
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
