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
) -> dict:
    """Creates a Google Slides presentation, optionally populating it with slides.

    Args:
        title: Presentation title.
        outline: Optional JSON array of slide objects. Each object must have
                 "title" (str) and "body" (str, bullet points separated by \\n).
                 Example: '[{"title": "Intro", "body": "• Point 1\\n• Point 2"}]'
    """
    try:
        creds = _credentials(tool_context)
        presentation_id = SlidesService.create_presentation(title, credentials=creds)
        url = f"https://docs.google.com/presentation/d/{presentation_id}/edit"

        created_slides = []
        if outline:
            try:
                slides_data = json.loads(outline) if isinstance(outline, str) else outline
            except json.JSONDecodeError as e:
                return {"status": "error", "message": f"Invalid outline JSON: {e}"}

            for slide in slides_data:
                slide_title = slide.get("title", "")
                body = slide.get("body", "")
                notes = slide.get("speaker_notes", "")
                slide_id = SlidesService.add_slide_with_content(
                    presentation_id,
                    title=slide_title,
                    body=body,
                    speaker_notes=notes,
                    credentials=creds,
                )
                created_slides.append({"slide_id": slide_id, "title": slide_title})

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
        body: Slide body text. Use \\n to separate bullet points.
        speaker_notes: Optional presenter notes for this slide.
    """
    try:
        creds = _credentials(tool_context)
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
) -> dict:
    """Inserts an image from a public URL into an existing slide.

    Args:
        presentation_id: The presentation ID.
        slide_id: The objectId of the slide to insert the image into.
        image_url: Publicly accessible image URL (GCS public URL or HTTPS).
    """
    try:
        creds = _credentials(tool_context)
        image_id = SlidesService.insert_image(
            presentation_id,
            slide_id=slide_id,
            image_url=image_url,
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
