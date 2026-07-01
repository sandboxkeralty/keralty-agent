"""End-to-end RAG pipeline orchestrator.

Stages:
  1. Multi-query expansion    (E4/E6) — 3 Gemini rewrites
  2. Hybrid retrieval         (E4/E5) — BM25 + dense + RRF
  3. Neighbor expansion       (E3)    — pull ±1 chunk around top results
  4. Gemini rerank            (E7/E8) — dynamic cutoff, recall preservation
  5. Coverage check           (E9)    — abstain when concept recall < threshold
  6. Context assembly                 — build [[filename:pN]] citation blocks

The KnowledgeAgent system prompt enforces the remaining generation guardrails
(E10-E16): citation enforcement, grounding, completeness, entity consistency.
"""

import os
import json
from dataclasses import dataclass, field
from typing import List, Optional

from config import settings


@dataclass
class RAGResult:
    chunks: list = field(default_factory=list)   # List[RetrievedChunk]
    query_variants: List[str] = field(default_factory=list)
    should_abstain: bool = False
    abstain_reason: str = ""
    context_text: str = ""
    citations: List[dict] = field(default_factory=list)
    coverage: float = 0.0


# ── Query rewriting ───────────────────────────────────────────────────────────

async def _rewrite_queries(query: str, n: int = 3) -> List[str]:
    """Generate n semantic variants of the query (E4/E6 fix)."""
    try:
        from google import genai

        if os.getenv("GOOGLE_GENAI_USE_VERTEXAI") == "1":
            client = genai.Client(
                vertexai=True,
                project=settings.GOOGLE_CLOUD_PROJECT,
                location=settings.GOOGLE_CLOUD_REGION,
            )
        else:
            client = genai.Client(api_key=settings.GOOGLE_API_KEY)

        prompt = (
            f"Generate {n} semantically different reformulations of this search query "
            f"for a corporate healthcare knowledge base (Keralty).\n"
            f"Capture different angles, synonyms, and interpretations.\n"
            f"Return ONLY a JSON array of strings.\n\n"
            f"Query: {query}"
        )
        resp = await client.aio.models.generate_content(
            model=settings.GEMINI_FLASH_MODEL,
            contents=prompt,
            config=genai.types.GenerateContentConfig(temperature=0.3, max_output_tokens=256),
        )
        raw = resp.text.strip()
        start, end = raw.find("["), raw.rfind("]") + 1
        variants: List[str] = json.loads(raw[start:end]) if start >= 0 else []
        return [v for v in variants[:n] if isinstance(v, str)]
    except Exception as exc:
        print(f"[pipeline] query rewrite failed: {exc}")
        return []


# ── Coverage check (E9 abstain gate) ─────────────────────────────────────────

_STOPWORDS = {
    "el", "la", "los", "las", "de", "en", "y", "a", "que", "un", "una",
    "the", "is", "in", "of", "and", "a", "to", "for", "with", "on",
}


def _concept_recall(chunks: list, query: str) -> float:
    keywords = {w for w in query.lower().split() if len(w) > 2 and w not in _STOPWORDS}
    if not keywords:
        return 1.0
    combined = " ".join(c.text.lower() for c in chunks)
    return sum(1 for w in keywords if w in combined) / len(keywords)


# ── Context assembly ──────────────────────────────────────────────────────────

def _build_context(chunks: list) -> tuple:
    """Returns (context_string, citations_list)."""
    parts: List[str] = []
    citations: List[dict] = []
    seen_cids: set = set()

    for chunk in chunks:
        if chunk.chunk_id in seen_cids:
            continue
        seen_cids.add(chunk.chunk_id)
        ref = f"[[{chunk.filename}:p{chunk.page_or_row}]]"
        parts.append(f"{ref}\n{chunk.text}")
        citations.append({
            "filename": chunk.filename,
            "page_or_row": chunk.page_or_row,
            "chunk_id": chunk.chunk_id,
            "snippet": chunk.text[:140],
        })

    return "\n\n---\n\n".join(parts), citations


# ── Main entry point ──────────────────────────────────────────────────────────

async def retrieve_for_query(
    query: str,
    k_dense: int = 30,
    k_sparse: int = 30,
    k_fused: int = 20,
    rerank_top_k: int = 8,
    neighbor_window: int = 1,
    abstain_threshold: float = 0.5,
    rewrite_count: int = 3,
) -> RAGResult:
    from services.rag.retriever import retrieve
    from services.rag.reranker import rerank

    # Stage 1: Multi-query expansion
    variants = await _rewrite_queries(query, n=rewrite_count)

    # Stage 2+3: Hybrid retrieve + neighbor expansion
    candidates = retrieve(
        query,
        query_variants=variants,
        k_dense=k_dense,
        k_sparse=k_sparse,
        k_fused=k_fused,
        neighbor_window=neighbor_window,
    )

    if not candidates:
        return RAGResult(
            query_variants=variants,
            should_abstain=True,
            abstain_reason=(
                "No se encontraron documentos relevantes en la Knowledge Base de Keralty. "
                "Asegúrate de que el documento esté indexado o reformula la pregunta."
            ),
        )

    # Stage 4: Rerank
    top_chunks = await rerank(query, candidates, top_k=rerank_top_k)

    # Stage 5: Coverage / abstain
    coverage = _concept_recall(top_chunks, query)
    should_abstain = coverage < abstain_threshold

    # Stage 6: Context
    context_text, citations = _build_context(top_chunks)

    return RAGResult(
        chunks=top_chunks,
        query_variants=variants,
        should_abstain=should_abstain,
        abstain_reason=(
            f"Cobertura conceptual insuficiente ({coverage:.0%}). "
            "Reformula la pregunta o verifica que el documento relevante esté en la KB."
            if should_abstain else ""
        ),
        context_text=context_text,
        citations=citations,
        coverage=coverage,
    )
