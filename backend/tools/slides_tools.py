from google.adk.tools import ToolContext
from services.slides import SlidesService
from services.firestore import FirestoreService
import uuid

async def slides_create(title: str, tool_context: ToolContext) -> dict:
    try:
        presentation_id = SlidesService.create_presentation(title)
        return {"status": "success", "presentation_id": presentation_id}
    except Exception as e:
        return {"status": "error", "message": str(e)}

async def slides_update(presentation_id: str, slide_title: str, slide_subtitle: str, tool_context: ToolContext) -> dict:
    """Updates the content of a Google Slide. This requires human approval.
    """
    task_id = str(uuid.uuid4())
    user_id = getattr(tool_context, "session", None).user_id if getattr(tool_context, "session", None) else "sandbox-user"
    
    FirestoreService.create_task(task_id, {
        "type": "slides_update",
        "presentation_id": presentation_id,
        "slide_title": slide_title,
        "slide_subtitle": slide_subtitle,
        "status": "pending",
        "user_id": user_id
    })
    
    return {"status": "pending_approval", "task_id": task_id, "message": "Task submitted for user approval"}

async def slides_add_image(presentation_id: str, slide_id: str, image_url: str, tool_context: ToolContext) -> dict:
    # This also modifies, so we generate a pending task
    task_id = str(uuid.uuid4())
    user_id = getattr(tool_context, "session", None).user_id if getattr(tool_context, "session", None) else "sandbox-user"
    
    FirestoreService.create_task(task_id, {
        "type": "slides_add_image",
        "presentation_id": presentation_id,
        "slide_id": slide_id,
        "image_url": image_url,
        "status": "pending",
        "user_id": user_id
    })
    return {"status": "pending_approval", "task_id": task_id, "message": "Task submitted for user approval"}
