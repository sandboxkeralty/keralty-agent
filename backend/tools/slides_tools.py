"""Slides tools — direct write operations (no HITL).

The approval gate lives in the VisualAgent instruction: the agent must call
approval_create + receive [APROBADO] BEFORE calling any of these tools.
"""

import json
import uuid
from typing import Optional

from google.adk.tools import ToolContext

from services.slides import SlidesService
from tools._auth import _credentials


def _user_id(tool_context) -> str:
    state = getattr(tool_context, "state", {}) if tool_context else {}
    return state.get("user_id") or "sandbox-user"


async def slides_create(
    title: str,
    tool_context: ToolContext,
    outline: Optional[str] = None,
    template: Optional[str] = None,
) -> dict:
    """Creates a themed Google Slides presentation from a designed outline.

    The deck is created from a corporate template (inheriting its fonts,
    colors and backgrounds) when one is configured.

    Args:
        title: Presentation title.
        template: Which corporate template to start from — "keralty" (default,
            general executive deck), "presidencia_corporativo" (formal
            Presidencia deck), or "presidencia_estandar" (content-richer
            Presidencia variant). Invalid/omitted values use "keralty".
        outline: JSON array of slide spec objects. Each spec supports:
            layout: "cover" | "section" | "content" | "two_column" |
                    "title_only" | "quote" | "big_number" | "closing"
                    (default "content")
            title: slide title (an assertion, not a label)
            subtitle: for cover/section/closing
            bullets: list of short strings (preferred over "body")
            body: legacy alternative — bullet lines joined with \\n
            columns: for two_column — exactly 2 of {"heading": str, "bullets": [str]}
            quote + attribution: for layout "quote"
            number + caption: for layout "big_number" (e.g. "87%" / "satisfacción")
            image_url + image_placement ("full_bleed"|"right_half"|"left_half"|"centered")
            speaker_notes: str
            background_color: "#RRGGBB" (optional, use sparingly)
        Example:
        '[{"layout":"cover","title":"Estrategia Digital 2026","subtitle":"Comité Ejecutivo — Julio 2026"},
          {"layout":"content","title":"La agenda cubre tres frentes","bullets":["Contexto del mercado","Avances del plan","Próximos pasos"]},
          {"layout":"two_column","title":"Dos modelos, un objetivo","columns":[{"heading":"Presencial","bullets":["Red propia","93 centros"]},{"heading":"Digital","bullets":["Telemedicina","IA clínica"]}]},
          {"layout":"big_number","number":"87%","caption":"satisfacción de pacientes en 2025"},
          {"layout":"title_only","title":"La experiencia del paciente es el centro","image_url":"https://...","image_placement":"full_bleed"},
          {"layout":"closing","title":"Gracias","subtitle":"Preguntas y siguientes pasos"}]'
    """
    try:
        creds = _credentials(tool_context)
        presentation_id = SlidesService.create_presentation(
            title, credentials=creds, template_key=template or "keralty")
        url = f"https://docs.google.com/presentation/d/{presentation_id}/edit"

        created_slides = []
        if outline:
            try:
                slides_data = json.loads(outline) if isinstance(outline, str) else outline
            except json.JSONDecodeError as e:
                return {"status": "error", "message": f"Invalid outline JSON: {e}"}

            # Resolve the deck's layout inventory once; every slide reuses it.
            try:
                layout_map = SlidesService.resolve_layouts(presentation_id, credentials=creds)
            except Exception:
                layout_map = {}

            for spec in slides_data:
                slide_id = SlidesService.add_designed_slide(
                    presentation_id, spec, layout_map, credentials=creds,
                )
                created_slides.append({
                    "slide_id": slide_id,
                    "title": spec.get("title", spec.get("number", spec.get("quote", ""))),
                    "layout": spec.get("layout", "content"),
                })

        return {
            "status": "success",
            "presentation_id": presentation_id,
            "url": url,
            "slides_created": len(created_slides),
            "slides": created_slides,
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


async def slides_add_slide(
    presentation_id: str,
    slide_title: str,
    body: str,
    tool_context: ToolContext,
    speaker_notes: Optional[str] = None,
) -> dict:
    """Adds a single slide with content to an existing presentation.

    Args:
        presentation_id: The presentation to update.
        slide_title: Title of the new slide.
        body: Slide body text. Use \\n to separate bullet points. May also be a
            JSON object string with the full slide spec schema documented in
            slides_create (layout, bullets, columns, quote, number, image_url…).
        speaker_notes: Optional presenter notes for this slide.
    """
    try:
        creds = _credentials(tool_context)
        spec = None
        if body and body.strip().startswith("{"):
            try:
                spec = json.loads(body)
            except json.JSONDecodeError:
                spec = None
        if spec is not None:
            spec.setdefault("title", slide_title)
            if speaker_notes:
                spec.setdefault("speaker_notes", speaker_notes)
            layout_map = SlidesService.resolve_layouts(presentation_id, credentials=creds)
            slide_id = SlidesService.add_designed_slide(
                presentation_id, spec, layout_map, credentials=creds,
            )
        else:
            slide_id = SlidesService.add_slide_with_content(
                presentation_id,
                title=slide_title,
                body=body,
                speaker_notes=speaker_notes or "",
                credentials=creds,
            )
        return {
            "status": "success",
            "presentation_id": presentation_id,
            "slide_id": slide_id,
            "url": f"https://docs.google.com/presentation/d/{presentation_id}/edit",
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


async def slides_add_image(
    presentation_id: str,
    slide_id: str,
    image_url: str,
    tool_context: ToolContext,
    placement: Optional[str] = None,
) -> dict:
    """Inserts an image from a public URL into an existing slide.

    Args:
        presentation_id: The presentation ID.
        slide_id: The objectId of the slide to insert the image into.
        image_url: Publicly accessible image URL (GCS public URL or HTTPS).
        placement: Optional preset position/size — one of "full_bleed",
            "right_half", "left_half", "centered". Default "right_half".
    """
    try:
        creds = _credentials(tool_context)
        image_id = SlidesService.insert_image(
            presentation_id,
            slide_id=slide_id,
            image_url=image_url,
            placement=placement or "right_half",
            credentials=creds,
        )
        return {
            "status": "success",
            "presentation_id": presentation_id,
            "slide_id": slide_id,
            "image_id": image_id,
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


async def slides_get(presentation_id: str, tool_context: ToolContext) -> dict:
    """Returns metadata for a presentation including all slide IDs and titles.

    Args:
        presentation_id: The presentation ID.
    """
    try:
        creds = _credentials(tool_context)
        pres = SlidesService.get_presentation(presentation_id, credentials=creds)
        slides = []
        for slide in pres.get("slides", []):
            slide_id = slide.get("objectId", "")
            title = ""
            for element in slide.get("pageElements", []):
                shape = element.get("shape", {})
                placeholder = shape.get("placeholder", {})
                if placeholder.get("type") == "TITLE":
                    text_content = shape.get("text", {}).get("textElements", [])
                    title = "".join(
                        e.get("textRun", {}).get("content", "") for e in text_content
                    ).strip()
            slides.append({"slide_id": slide_id, "title": title})
        return {
            "status": "success",
            "presentation_id": presentation_id,
            "title": pres.get("title", ""),
            "slide_count": len(slides),
            "slides": slides,
            "url": f"https://docs.google.com/presentation/d/{presentation_id}/edit",
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}
