from google.adk.tools import ToolContext

async def image_generate(prompt: str, tool_context: ToolContext) -> dict:
    return {"status": "success", "image_url": "https://example.com/image.jpg"}
