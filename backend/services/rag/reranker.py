"""Gemini LLM reranker — E7/E8 guardrails.

Uses Gemini to score candidate chunks 0–1 against the query.
Dynamic cutoff: stop including chunks when the relevance gap exceeds gap_threshold.
Recall preservation: if result set falls below min_k, add back high-RRF items.
"""

import json
from typing import List

from services.rag.retriever import RetrievedChunk


async def rerank(
    query: str,
    candidates: List[RetrievedChunk],
    top_k: int = 8,
    min_k: int = 4,
    gap_threshold: float = 0.2,
) -> List[RetrievedChunk]:
    if not candidates:
        return []
    if len(candidates) <= min_k:
        return candidates

    snippets = "\n".join(
        f"[{i}] {c.text[:280].replace(chr(10), ' ')}"
        for i, c in enumerate(candidates)
    )

    prompt = (
        f"You are a relevance judge for a corporate knowledge base.\n\n"
        f"Query: {query}\n\n"
        f"Rate each passage 0.0 (irrelevant) to 1.0 (directly answers the query).\n\n"
        f"Passages:\n{snippets}\n\n"
        f"Reply with ONLY a JSON array of {len(candidates)} numbers, e.g. [0.9, 0.3, 0.7]"
    )

    try:
        from google import genai
        from config import settings
        from services.genai_client import get_genai_client

        client = get_genai_client()

        response = await client.aio.models.generate_content(
            model=settings.GEMINI_FLASH_MODEL,
            contents=prompt,
            # thinking_budget=0 is mandatory: gemini-2.5-flash spends "thinking"
            # tokens out of max_output_tokens first, so without this the 512-token
            # budget is consumed before any JSON is emitted → empty response.text →
            # json.loads raises "Expecting value" → reranker silently degrades to raw
            # RRF order (the documented latent bug, confirmed firing in prod).
            config=genai.types.GenerateContentConfig(
                temperature=0.0,
                max_output_tokens=512,
                thinking_config=genai.types.ThinkingConfig(thinking_budget=0),
            ),
        )
        raw = (response.text or "").strip()
        start, end = raw.find("["), raw.rfind("]") + 1
        scores: List[float] = json.loads(raw[start:end]) if start >= 0 else []

        if len(scores) != len(candidates):
            return candidates[:top_k]

        scored = sorted(zip(candidates, scores), key=lambda x: x[1], reverse=True)

        # Dynamic cutoff
        result: List[RetrievedChunk] = [scored[0][0]]
        for i in range(1, len(scored)):
            if len(result) >= top_k:
                break
            gap = scored[i - 1][1] - scored[i][1]
            if gap > gap_threshold and len(result) >= min_k:
                break
            result.append(scored[i][0])

        # Recall preservation — E7
        if len(result) < min_k:
            seen = {c.chunk_id for c in result}
            for c in sorted(candidates, key=lambda x: x.rrf_score, reverse=True):
                if c.chunk_id not in seen:
                    result.append(c)
                if len(result) >= min_k:
                    break

        return result

    except Exception as exc:
        print(f"[reranker] fallback to RRF order: {exc}")
        return candidates[:top_k]
