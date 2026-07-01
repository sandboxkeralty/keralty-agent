"""Token-aware document chunker — E1/E2/E3 guardrails.

Pipeline:
  1. Structure-aware split  — break on headings and blank lines first.
  2. Token refine           — merge micro-blocks, split oversized ones at sentences.
  3. Overlap                — append the first 15 % of the next chunk to each chunk.
  4. Coalesce               — merge chunks < MIN_TOKENS with their successor.
  5. Neighbor links         — wire prev/next chunk IDs for expansion at retrieval time.
"""

import re
import hashlib
import uuid
from dataclasses import dataclass, field
from typing import List, Optional


# 1 token ≈ 4 characters (avoids tokenizer dependency while staying accurate enough)
def _approx_tokens(text: str) -> int:
    return max(1, len(text) // 4)


@dataclass
class Chunk:
    chunk_id: str
    doc_id: str
    filename: str
    filetype: str
    text: str
    token_count: int
    page_or_row: int
    hash: str
    chunk_index: int
    neighbor_prev: Optional[str] = None
    neighbor_next: Optional[str] = None


_HEADING_RE = re.compile(r"^#{1,6}\s+", re.MULTILINE)
_SENTENCE_END_RE = re.compile(r"(?<=[.!?])\s+")


def _split_paragraphs(text: str) -> List[str]:
    """Split on headings + double newlines, keeping headings attached to their content."""
    segments = re.split(r"(\n#{1,6} [^\n]+)", text)
    blocks: List[str] = []
    i = 0
    while i < len(segments):
        seg = segments[i]
        if _HEADING_RE.match(seg.lstrip("\n")):
            following = segments[i + 1] if i + 1 < len(segments) else ""
            blocks.append(seg.strip() + "\n" + following)
            i += 2
        else:
            for para in re.split(r"\n{2,}", seg):
                para = para.strip()
                if para:
                    blocks.append(para)
            i += 1
    return [b for b in blocks if b.strip()]


def _split_sentences(text: str) -> List[str]:
    return [s.strip() for s in _SENTENCE_END_RE.split(text) if s.strip()]


def _merge_into_chunks(blocks: List[str], max_tokens: int) -> List[str]:
    """Greedy merge: accumulate until the next block would exceed max_tokens.
    Oversized individual blocks are split at sentence boundaries.

    Measures the token count of the actual prospective joined string rather than
    summing each block's individually-truncated approximation — summing
    per-block `len // 4` estimates systematically undercounts the true joined
    length (floor-division drift plus untracked join-separator characters),
    letting the buffer silently grow past max_tokens over many small blocks.
    """
    chunks: List[str] = []
    buf: List[str] = []

    for block in blocks:
        block_tok = _approx_tokens(block)

        if block_tok > max_tokens:
            # Flush accumulator first
            if buf:
                chunks.append(" ".join(buf))
                buf = []
            # Split oversized block at sentences
            sent_buf: List[str] = []
            for s in _split_sentences(block):
                candidate = " ".join(sent_buf + [s])
                if sent_buf and _approx_tokens(candidate) > max_tokens:
                    chunks.append(" ".join(sent_buf))
                    sent_buf = []
                sent_buf.append(s)
            if sent_buf:
                chunks.append(" ".join(sent_buf))
            continue

        candidate = " ".join(buf + [block])
        if buf and _approx_tokens(candidate) > max_tokens:
            chunks.append(" ".join(buf))
            buf = []

        buf.append(block)

    if buf:
        chunks.append(" ".join(buf))
    return chunks


def _apply_overlap(chunks: List[str], overlap_pct: float) -> List[str]:
    """Append the first `overlap_pct` fraction of the next chunk to each chunk."""
    result: List[str] = []
    for i, chunk in enumerate(chunks):
        if i + 1 < len(chunks):
            next_chunk = chunks[i + 1]
            n_chars = int(len(next_chunk) * overlap_pct)
            if n_chars > 0:
                tail = next_chunk[:n_chars]
                last_space = tail.rfind(" ")
                if last_space > 0:
                    tail = tail[:last_space]
                chunk = chunk.rstrip() + " " + tail.strip()
        result.append(chunk)
    return result


def _coalesce_small(chunks: List[str], min_tokens: int, max_tokens: int) -> List[str]:
    """Merge chunks < min_tokens with their successor, without exceeding max_tokens.

    A long run of tiny fragments (common in PDF extractions with broken paragraph
    structure — tables, forms, multi-column layouts) would otherwise cascade into
    one unbounded chunk, since merging always re-checks the newly-grown chunk
    against min_tokens with no upper bound.
    """
    result: List[str] = []
    i = 0
    while i < len(chunks):
        current = chunks[i]
        while (
            _approx_tokens(current) < min_tokens
            and i + 1 < len(chunks)
            and _approx_tokens(current) + _approx_tokens(chunks[i + 1]) <= max_tokens
        ):
            i += 1
            current = current + " " + chunks[i]
        result.append(current)
        i += 1
    return result


def chunk_document(
    text: str,
    doc_id: str,
    filename: str,
    filetype: str,
    target_tokens: int = 800,
    max_tokens: int = 1000,
    overlap_pct: float = 0.15,
    min_tokens: int = 120,
    start_page: int = 1,
) -> List[Chunk]:
    """Full chunking pipeline. Returns a list of Chunk objects with neighbor links."""
    paragraphs = _split_paragraphs(text)
    raw = _merge_into_chunks(paragraphs, max_tokens)
    raw = _coalesce_small(raw, min_tokens, max_tokens)
    raw = _apply_overlap(raw, overlap_pct)

    chunks: List[Chunk] = []
    for i, text_chunk in enumerate(raw):
        chunks.append(Chunk(
            chunk_id=f"chunk_{uuid.uuid4().hex}",
            doc_id=doc_id,
            filename=filename,
            filetype=filetype,
            text=text_chunk,
            token_count=_approx_tokens(text_chunk),
            page_or_row=start_page + i,
            hash=hashlib.sha256(text_chunk.encode()).hexdigest()[:16],
            chunk_index=i,
        ))

    # Wire neighbor links
    for i, chunk in enumerate(chunks):
        chunk.neighbor_prev = chunks[i - 1].chunk_id if i > 0 else None
        chunk.neighbor_next = chunks[i + 1].chunk_id if i + 1 < len(chunks) else None

    return chunks
