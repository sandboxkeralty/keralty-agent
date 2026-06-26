from google.adk.tools import ToolContext

async def kb_search(query: str, tool_context: ToolContext) -> dict:
    return {"status": "success", "results": []}

async def kb_get_person(name: str = None, role: str = None, department: str = None, tool_context: ToolContext = None) -> dict:
    return {"status": "success", "person": {"name": name or "John Doe", "role": role or "Executive", "email": "john.doe@keralty.com"}}

async def kb_get_department(department: str, tool_context: ToolContext) -> dict:
    return {"status": "success", "department": department, "description": "Core business unit"}

async def kb_get_org_chart(starting_from: str = "CEO", depth: int = 1, tool_context: ToolContext = None) -> dict:
    return {"status": "success", "org_chart": {"root": starting_from, "reports": []}}

async def kb_get_policy(topic: str, tool_context: ToolContext) -> dict:
    return {"status": "success", "policy": f"Policy for {topic}", "content": "..."}
