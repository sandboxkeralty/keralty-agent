"""KB tools — all backed by the RAG pipeline.

Every tool runs the full retrieve→rerank pipeline with a structured query,
then returns the top chunks as citations for the KnowledgeAgent to synthesize.
"""

from google.adk.tools import ToolContext


def _state(tool_context) -> dict:
    return getattr(tool_context, "state", {}) if tool_context else {}


async def kb_search(query: str, tool_context: ToolContext) -> dict:
    """Searches the Keralty corporate Knowledge Base using semantic + keyword retrieval.

    Args:
        query: Natural-language question or topic to search for.
    """
    try:
        from services.rag.pipeline import retrieve_for_query
        result = await retrieve_for_query(query)

        if result.should_abstain:
            return {
                "status": "abstain",
                "message": result.abstain_reason,
                "follow_ups": [
                    "¿Puedes reformular la pregunta con términos más específicos?",
                    "¿Qué documento específico buscas?",
                    "¿Cuál es el área o departamento relacionado?",
                ],
            }

        return {
            "status": "success",
            "query_variants": result.query_variants,
            "coverage": round(result.coverage, 2),
            "context": result.context_text,
            "citations": result.citations,
            "result_count": len(result.chunks),
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


async def kb_get_person(
    name: str = None,
    role: str = None,
    department: str = None,
    tool_context: ToolContext = None,
) -> dict:
    """Looks up a person in the Keralty organizational Knowledge Base.

    Args:
        name: Person's name (partial match supported).
        role: Job title or role to search for.
        department: Department or area name.
    """
    parts = []
    if name:
        parts.append(f"persona nombre: {name}")
    if role:
        parts.append(f"cargo: {role}")
    if department:
        parts.append(f"área departamento: {department}")

    query = "Información sobre " + ", ".join(parts) if parts else "directorio de personas Keralty"

    try:
        from services.rag.pipeline import retrieve_for_query
        result = await retrieve_for_query(query, rerank_top_k=5)

        if result.should_abstain:
            return {"status": "not_found", "message": result.abstain_reason}

        return {
            "status": "success",
            "context": result.context_text,
            "citations": result.citations,
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


async def kb_get_department(department: str, tool_context: ToolContext) -> dict:
    """Returns information about a Keralty department or business area.

    Args:
        department: Department or area name.
    """
    query = f"Departamento área {department}: estructura, funciones, responsables, objetivos"
    try:
        from services.rag.pipeline import retrieve_for_query
        result = await retrieve_for_query(query, rerank_top_k=6)

        if result.should_abstain:
            return {"status": "not_found", "message": result.abstain_reason}

        return {
            "status": "success",
            "department": department,
            "context": result.context_text,
            "citations": result.citations,
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


async def kb_get_org_chart(
    starting_from: str = "CEO",
    depth: int = 1,
    tool_context: ToolContext = None,
) -> dict:
    """Retrieves the organizational chart from the Knowledge Base.

    Args:
        starting_from: Starting node (e.g. 'CEO', 'VP de Operaciones').
        depth: Number of reporting levels to retrieve (1–3).
    """
    query = (
        f"Organigrama estructura jerárquica Keralty desde {starting_from}, "
        f"{depth} niveles de reportes directos, quién reporta a quién"
    )
    try:
        from services.rag.pipeline import retrieve_for_query
        result = await retrieve_for_query(query, rerank_top_k=8)

        if result.should_abstain:
            return {"status": "not_found", "message": result.abstain_reason}

        return {
            "status": "success",
            "starting_from": starting_from,
            "depth": depth,
            "context": result.context_text,
            "citations": result.citations,
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


async def kb_get_policy(topic: str, tool_context: ToolContext) -> dict:
    """Retrieves corporate policies and procedures for a given topic.

    Args:
        topic: Policy topic (e.g. 'teletrabajo', 'protección de datos', 'viáticos').
    """
    query = (
        f"Política procedimiento normativa Keralty sobre {topic}: "
        "requisitos, pasos, responsables, excepciones, vigencia"
    )
    try:
        from services.rag.pipeline import retrieve_for_query
        result = await retrieve_for_query(query, rerank_top_k=6)

        if result.should_abstain:
            return {"status": "not_found", "message": result.abstain_reason}

        return {
            "status": "success",
            "topic": topic,
            "context": result.context_text,
            "citations": result.citations,
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}
