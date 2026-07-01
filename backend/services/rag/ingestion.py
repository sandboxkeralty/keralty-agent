"""Document ingestion pipeline: extract → chunk → embed → store.

Supported formats: PDF, DOCX, TXT, CSV, MD
"""

import io
import uuid

from config import settings


# ── Text extraction ───────────────────────────────────────────────────────────

def _extract_pdf(data: bytes) -> str:
    from pypdf import PdfReader
    reader = PdfReader(io.BytesIO(data))
    pages = [page.extract_text() or "" for page in reader.pages]
    return "\n\n".join(p for p in pages if p.strip())


def _extract_docx(data: bytes) -> str:
    import docx
    doc = docx.Document(io.BytesIO(data))
    return "\n\n".join(p.text for p in doc.paragraphs if p.text.strip())


def _extract_csv(data: bytes) -> str:
    import csv, io as _io
    text = data.decode("utf-8", errors="replace")
    reader = csv.DictReader(_io.StringIO(text))
    rows = [
        "Row {}: {}".format(i + 1, " | ".join(f"{k}: {v}" for k, v in row.items()))
        for i, row in enumerate(reader)
    ]
    return "\n".join(rows)


def extract_text(data: bytes, filetype: str) -> str:
    ft = filetype.lower().lstrip(".")
    if ft == "pdf":
        return _extract_pdf(data)
    if ft in ("docx", "doc"):
        return _extract_docx(data)
    if ft == "csv":
        return _extract_csv(data)
    # txt / md / fallback
    return data.decode("utf-8", errors="replace")


# ── GCS upload ────────────────────────────────────────────────────────────────

def _upload_to_gcs(data: bytes, filename: str, doc_id: str) -> str:
    from google.cloud import storage
    client = storage.Client(project=settings.GOOGLE_CLOUD_PROJECT)
    bucket = client.bucket(settings.KB_GCS_BUCKET)
    blob = bucket.blob(f"documents/{doc_id}/{filename}")
    blob.upload_from_string(data)
    return f"gs://{settings.KB_GCS_BUCKET}/documents/{doc_id}/{filename}"


# ── Main pipeline ─────────────────────────────────────────────────────────────

async def ingest_document(
    data: bytes,
    filename: str,
    filetype: str,
    target_tokens: int = 800,
    max_tokens: int = 1000,
    overlap_pct: float = 0.15,
    min_tokens: int = 120,
) -> dict:
    """Full ingestion. Returns metadata dict with doc_id and chunk_count."""
    from services.rag.chunker import chunk_document
    from services.rag.embedder import embed_texts
    from services.rag.store import save_chunks, save_doc_metadata
    from services.rag.retriever import invalidate_cache

    doc_id = str(uuid.uuid4())

    # 1. Extract
    text = extract_text(data, filetype)
    if not text.strip():
        raise ValueError(f"No extractable text found in '{filename}'.")

    # 2. Chunk  (E1/E2/E3)
    chunks = chunk_document(
        text=text,
        doc_id=doc_id,
        filename=filename,
        filetype=filetype,
        target_tokens=target_tokens,
        max_tokens=max_tokens,
        overlap_pct=overlap_pct,
        min_tokens=min_tokens,
    )

    # 3. Embed
    texts = [c.text for c in chunks]
    embeddings = embed_texts(texts, task_type="RETRIEVAL_DOCUMENT")

    # 4. Persist chunks + embeddings
    save_chunks(chunks, embeddings)

    # 5. Store original in GCS
    gcs_path = _upload_to_gcs(data, filename, doc_id)

    # 6. Doc metadata
    save_doc_metadata(doc_id, filename, filetype, len(chunks), gcs_path)

    # 7. Invalidate BM25 cache so next retrieval picks up new chunks
    invalidate_cache()

    return {
        "doc_id": doc_id,
        "filename": filename,
        "filetype": filetype,
        "chunk_count": len(chunks),
        "gcs_path": gcs_path,
    }
