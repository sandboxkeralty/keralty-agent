from google.adk.tools import ToolContext

async def email_list(account_id: str = "primary", folder: str = "inbox", max_results: int = 50, tool_context: ToolContext = None) -> dict:
    return {"status": "success", "emails": []}

async def email_read(thread_id: str, tool_context: ToolContext) -> dict:
    return {"status": "success", "thread": {"id": thread_id, "messages": []}}

async def email_search(query: str, max_results: int = 10, tool_context: ToolContext = None) -> dict:
    return {"status": "success", "results": []}

async def email_summarize_thread(thread_id: str, tool_context: ToolContext) -> dict:
    return {"status": "success", "summary": "Summary of the thread..."}

async def email_draft(to: str, subject: str, body: str, tool_context: ToolContext) -> dict:
    return {"status": "success", "draft_id": "draft_123"}

async def email_send(draft_id: str, tool_context: ToolContext) -> dict:
    return {"status": "success", "sent": True}

async def email_track(message_id: str, tool_context: ToolContext) -> dict:
    return {"status": "success", "tracking": True}

async def email_get_tracking(tool_context: ToolContext) -> dict:
    return {"status": "success", "tracked_emails": []}

async def email_generate_followup(tracking_id: str, tool_context: ToolContext) -> dict:
    return {"status": "success", "draft_id": "followup_123"}
