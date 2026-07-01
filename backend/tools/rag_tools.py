"""Generic RAG tools available to any agent that needs KB context injection."""

from google.adk.tools import ToolContext


async def rag_retrieve(query: str, tool_context: ToolContext) -> dict:
    """Retrieves relevant KB chunks for a given query using hybrid RAG.

    Args:
        query: The search query or question.
    """
    try:
        from services.rag.pipeline import retrieve_for_query
        result = await retrieve_for_query(query)

        if result.should_abstain:
            return {
                "status": "no_results",
                "message": result.abstain_reason,
                "citations": [],
                "context": "",
            }

        return {
            "status": "success",
            "context": result.context_text,
            "citations": result.citations,
            "coverage": round(result.coverage, 2),
            "chunk_count": len(result.chunks),
        }
    except Exception as e:
        return {"status": "error", "error": str(e), "context": "", "citations": []}


async def context_inject(context_id: str, tool_context: ToolContext) -> dict:
    """Injects a specific named KB context into the agent's reasoning flow.

    Args:
        context_id: Identifier for a known context type:
                    'org_chart', 'policies', 'strategy', 'directory', or any free-text topic.
    """
    # Map well-known context IDs to structured queries
    _CONTEXT_QUERIES = {
        "org_chart": "Organigrama completo Keralty estructura jerárquica líderes",
        "policies": "Políticas y procedimientos corporativos Keralty vigentes",
        "strategy": "Estrategia corporativa misión visión valores objetivos Keralty",
        "directory": "Directorio de personas roles emails contactos Keralty",
    }
    query = _CONTEXT_QUERIES.get(context_id, context_id)

    try:
        from services.rag.pipeline import retrieve_for_query
        result = await retrieve_for_query(query, rerank_top_k=10)
        return {
            "status": "success",
            "context_id": context_id,
            "context": result.context_text,
            "citations": result.citations,
            "injected": True,
        }
    except Exception as e:
        return {"status": "error", "error": str(e), "injected": False}
