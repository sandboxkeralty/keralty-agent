"""Vertex AI text-embedding-005 wrapper with batching and task-type support."""

from typing import List
from config import settings

_MODEL_NAME = "text-embedding-005"
_BATCH_SIZE = 250  # Vertex AI max per request


def _init_vertexai():
    import vertexai
    vertexai.init(project=settings.GOOGLE_CLOUD_PROJECT, location=settings.GOOGLE_CLOUD_REGION)


def embed_texts(texts: List[str], task_type: str = "RETRIEVAL_DOCUMENT") -> List[List[float]]:
    """Returns one embedding vector per input text.

    task_type: "RETRIEVAL_DOCUMENT" for indexing, "RETRIEVAL_QUERY" for queries.
    """
    _init_vertexai()
    from vertexai.language_models import TextEmbeddingModel, TextEmbeddingInput

    model = TextEmbeddingModel.from_pretrained(_MODEL_NAME)
    all_embeddings: List[List[float]] = []

    for i in range(0, len(texts), _BATCH_SIZE):
        batch = texts[i : i + _BATCH_SIZE]
        inputs = [TextEmbeddingInput(text=t, task_type=task_type) for t in batch]
        results = model.get_embeddings(inputs)
        all_embeddings.extend(r.values for r in results)

    return all_embeddings


def embed_query(query: str) -> List[float]:
    return embed_texts([query], task_type="RETRIEVAL_QUERY")[0]
