from google.adk.tools import ToolContext

async def slides_create(title: str, tool_context: ToolContext) -> dict:
    return {"status": "success", "presentation_id": "p_123"}

async def slides_update(presentation_id: str, slide_content: str, tool_context: ToolContext) -> dict:
    return {"status": "success", "updated": True}

async def slides_add_image(presentation_id: str, slide_id: str, image_url: str, tool_context: ToolContext) -> dict:
    return {"status": "success", "updated": True}
