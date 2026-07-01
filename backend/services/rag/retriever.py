"""Hybrid retriever: BM25 (sparse) + dense embeddings + Reciprocal Rank Fusion.

Implements E4-E6 guardrails:
  E4 Missed Retrieval  — multi-query expansion + RRF fusion
  E5 Low Relevance     — hybrid retrieval (BM25 + dense)
  E6 Semantic Drift    — RRF balances lexical vs semantic signal

Module-level cache: corpus and BM25 index are loaded once per container
instance and invalidated after new document ingestion.
"""

import threading
from dataclasses import dataclass
from typing import Dict, List, Optional

_LOCK = threading.Lock()
_corpus_cache: Optional[List[dict]] = None
_bm25_index = None


@dataclass
class RetrievedChunk:
    chunk_id: str
    doc_id: str
    filename: str
    filetype: str
    text: str
    page_or_row: int
    rrf_score: float
    neighbor_prev: Optional[str] = None
    neighbor_next: Optional[str] = None


# ── Cache management ──────────────────────────────────────────────────────────

def _ensure_corpus() -> List[dict]:
    global _corpus_cache, _bm25_index
    with _LOCK:
        if _corpus_cache is not None:
            return _corpus_cache

        from services.rag.store import load_all_chunks
        _corpus_cache = load_all_chunks()

        if _corpus_cache:
            from rank_bm25 import BM25Okapi
            tokenized = [c["text"].lower().split() for c in _corpus_cache]
            _bm25_index = BM25Okapi(tokenized)

    return _corpus_cache or []


def invalidate_cache() -> None:
    global _corpus_cache, _bm25_index
    with _LOCK:
        _corpus_cache = None
        _bm25_index = None


# ── Dense retrieval ───────────────────────────────────────────────────────────

def _cosine(a: List[float], b: List[float]) -> float:
    import numpy as np
    va, vb = np.array(a, dtype=float), np.array(b, dtype=float)
    denom = np.linalg.norm(va) * np.linalg.norm(vb)
    return float(np.dot(va, vb) / denom) if denom > 0 else 0.0


def _dense_retrieve(query_emb: List[float], corpus: List[dict], k: int) -> List[tuple]:
    """Returns [(chunk_dict, score)] sorted descending."""
    import numpy as np
    embeddings = [c.get("embedding") for c in corpus]
    valid = [(c, e) for c, e in zip(corpus, embeddings) if e]
    if not valid:
        return []
    chunks_valid, emb_matrix = zip(*valid)
    matrix = np.array(emb_matrix, dtype=float)
    qv = np.array(query_emb, dtype=float)
    norms = np.linalg.norm(matrix, axis=1) * np.linalg.norm(qv)
    scores = np.divide(matrix @ qv, norms, out=np.zeros(len(matrix)), where=norms > 0)
    top_idx = np.argsort(scores)[::-1][:k]
    return [(chunks_valid[i], float(scores[i])) for i in top_idx]


# ── Sparse retrieval (BM25) ───────────────────────────────────────────────────

def _sparse_retrieve(query: str, corpus: List[dict], k: int) -> List[tuple]:
    """Returns [(corpus_index, score)] sorted descending."""
    if _bm25_index is None or not corpus:
        return []
    raw_scores = _bm25_index.get_scores(query.lower().split())
    indexed = sorted(enumerate(raw_scores), key=lambda x: x[1], reverse=True)
    return [(i, float(s)) for i, s in indexed[:k] if s > 0]


# ── Reciprocal Rank Fusion ────────────────────────────────────────────────────

def _rrf(
    dense_lists: List[List[tuple]],
    sparse_lists: List[List[tuple]],
    corpus: List[dict],
    k_rrf: int = 60,
    top_k: int = 20,
) -> List[tuple]:
    """Fuse multiple ranked lists using RRF. Returns [(chunk_dict, rrf_score)]."""
    scores: Dict[str, float] = {}
    chunk_by_id: Dict[str, dict] = {}

    for dense_results in dense_lists:
        for rank, (chunk, _) in enumerate(dense_results):
            cid = chunk["chunk_id"]
            chunk_by_id[cid] = chunk
            scores[cid] = scores.get(cid, 0.0) + 1.0 / (k_rrf + rank + 1)

    for sparse_results in sparse_lists:
        for rank, (idx, _) in enumerate(sparse_results):
            c = corpus[idx]
            cid = c["chunk_id"]
            chunk_by_id[cid] = c
            scores[cid] = scores.get(cid, 0.0) + 1.0 / (k_rrf + rank + 1)

    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:top_k]
    return [(chunk_by_id[cid], score) for cid, score in ranked if cid in chunk_by_id]


# ── Neighbor expansion ────────────────────────────────────────────────────────

def _expand_neighbors(
    fused: List[tuple],
    corpus_by_id: Dict[str, dict],
    window: int = 1,
) -> List[tuple]:
    """Pull in adjacent chunks (±window) around top results (E3 fix)."""
    seen = {c["chunk_id"] for c, _ in fused}
    result = list(fused)

    for chunk, score in fused[:10]:  # only expand top 10 to limit bloat
        for neighbor_id in [chunk.get("neighbor_prev"), chunk.get("neighbor_next")]:
            if neighbor_id and neighbor_id not in seen and neighbor_id in corpus_by_id:
                result.append((corpus_by_id[neighbor_id], 0.0))
                seen.add(neighbor_id)

    return result


# ── Public API ────────────────────────────────────────────────────────────────

def retrieve(
    query: str,
    query_variants: Optional[List[str]] = None,
    k_dense: int = 30,
    k_sparse: int = 30,
    k_fused: int = 20,
    neighbor_window: int = 1,
) -> List[RetrievedChunk]:
    corpus = _ensure_corpus()
    if not corpus:
        return []

    corpus_by_id = {c["chunk_id"]: c for c in corpus}
    all_queries = [query] + (query_variants or [])

    from services.rag.embedder import embed_query

    dense_lists: List[List[tuple]] = []
    sparse_lists: List[List[tuple]] = []

    for q in all_queries:
        qemb = embed_query(q)
        dense_lists.append(_dense_retrieve(qemb, corpus, k_dense))
        sparse_lists.append(_sparse_retrieve(q, corpus, k_sparse))

    fused = _rrf(dense_lists, sparse_lists, corpus, top_k=k_fused)

    if neighbor_window > 0:
        fused = _expand_neighbors(fused, corpus_by_id, window=neighbor_window)

    return [
        RetrievedChunk(
            chunk_id=c["chunk_id"],
            doc_id=c.get("doc_id", ""),
            filename=c.get("filename", ""),
            filetype=c.get("filetype", ""),
            text=c.get("text", ""),
            page_or_row=c.get("page_or_row", 0),
            rrf_score=score,
            neighbor_prev=c.get("neighbor_prev"),
            neighbor_next=c.get("neighbor_next"),
        )
        for c, score in fused
    ]
