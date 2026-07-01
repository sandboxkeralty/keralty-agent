"""Firestore-backed chunk store.

Collections:
  kb_chunks    — one doc per chunk: text + embedding + metadata
  kb_documents — one doc per ingested file: metadata only
"""

import datetime
from typing import List, Optional

from google.cloud import firestore as _fs

from services.firestore import db
from services.rag.chunker import Chunk

_CHUNKS_COL = "kb_chunks"
_DOCS_COL = "kb_documents"


def save_chunks(chunks: List[Chunk], embeddings: List[List[float]]) -> None:
    """Write all chunks in Firestore batches (max 500 ops/batch)."""
    BATCH_SIZE = 499
    for start in range(0, len(chunks), BATCH_SIZE):
        batch = db.batch()
        for chunk, emb in zip(chunks[start:start + BATCH_SIZE], embeddings[start:start + BATCH_SIZE]):
            ref = db.collection(_CHUNKS_COL).document(chunk.chunk_id)
            batch.set(ref, {
                "chunk_id": chunk.chunk_id,
                "doc_id": chunk.doc_id,
                "filename": chunk.filename,
                "filetype": chunk.filetype,
                "text": chunk.text,
                "token_count": chunk.token_count,
                "page_or_row": chunk.page_or_row,
                "hash": chunk.hash,
                "chunk_index": chunk.chunk_index,
                "neighbor_prev": chunk.neighbor_prev,
                "neighbor_next": chunk.neighbor_next,
                "embedding": emb,
                "ingested_at": datetime.datetime.now(datetime.timezone.utc),
            })
        batch.commit()


def load_all_chunks() -> List[dict]:
    """Load all chunks (text + embedding) from Firestore."""
    return [d.to_dict() for d in db.collection(_CHUNKS_COL).stream()]


def get_chunk(chunk_id: str) -> Optional[dict]:
    doc = db.collection(_CHUNKS_COL).document(chunk_id).get()
    return doc.to_dict() if doc.exists else None


def delete_doc_chunks(doc_id: str) -> int:
    docs = list(db.collection(_CHUNKS_COL).where("doc_id", "==", doc_id).stream())
    batch = db.batch()
    for doc in docs:
        batch.delete(doc.reference)
    if docs:
        batch.commit()
    return len(docs)


def save_doc_metadata(doc_id: str, filename: str, filetype: str, chunk_count: int, gcs_path: str) -> None:
    db.collection(_DOCS_COL).document(doc_id).set({
        "doc_id": doc_id,
        "filename": filename,
        "filetype": filetype,
        "chunk_count": chunk_count,
        "gcs_path": gcs_path,
        "ingested_at": datetime.datetime.now(datetime.timezone.utc),
        "status": "indexed",
    })


def list_docs() -> List[dict]:
    docs = (
        db.collection(_DOCS_COL)
        .order_by("ingested_at", direction=_fs.Query.DESCENDING)
        .stream()
    )
    return [d.to_dict() for d in docs]


def delete_doc_metadata(doc_id: str) -> None:
    db.collection(_DOCS_COL).document(doc_id).delete()
