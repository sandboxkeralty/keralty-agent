"""Vertex AI text-embedding-005 wrapper with batching and task-type support."""

from typing import List
from config import settings

_MODEL_NAME = "text-embedding-005"
_MAX_BATCH_ITEMS = 250  # Vertex AI max items per request
_MAX_BATCH_TOKENS = 10000  # conservative pre-batching budget under the model's 20000-token
                           # per-request limit — a char-count heuristic can't precisely
                           # predict real tokenization (varies by language/content density),
                           # so this is a first line of defense, not a guarantee; see
                           # _embed_batch below for the actual correctness guarantee.


def _init_vertexai():
    import vertexai
    import google.auth
    # Explicit ADC credentials are load-bearing: with GOOGLE_API_KEY set in the
    # environment (the Gemini agents run on the AI Studio key), the vertexai SDK
    # silently prefers API-key transport, which has no project ("project 0")
    # and 403s on every model — embeddings and Imagen both broke this way.
    creds, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
    vertexai.init(project=settings.GOOGLE_CLOUD_PROJECT,
                  location=settings.GOOGLE_CLOUD_REGION, credentials=creds)


def _estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def _embed_batch(model, texts: List[str], task_type: str) -> List[List[float]]:
    """Embeds one batch, self-healing on a real "token count exceeded" error by
    splitting the batch in half and retrying each half — this is the actual
    correctness guarantee, since no character-count heuristic can precisely
    predict the model's real per-request token limit across languages/content.
    """
    from vertexai.language_models import TextEmbeddingInput

    inputs = [TextEmbeddingInput(text=t, task_type=task_type) for t in texts]
    try:
        results = model.get_embeddings(inputs)
        return [r.values for r in results]
    except Exception as e:
        if "token count" in str(e).lower() and len(texts) > 1:
            mid = len(texts) // 2
            return (
                _embed_batch(model, texts[:mid], task_type)
                + _embed_batch(model, texts[mid:], task_type)
            )
        raise


def embed_texts(texts: List[str], task_type: str = "RETRIEVAL_DOCUMENT") -> List[List[float]]:
    """Returns one embedding vector per input text.

    task_type: "RETRIEVAL_DOCUMENT" for indexing, "RETRIEVAL_QUERY" for queries.
    Batches respect both a max item count and a conservative max total token
    estimate per request; any batch that still exceeds the real per-request
    token limit gets split and retried by _embed_batch.
    """
    _init_vertexai()
    from vertexai.language_models import TextEmbeddingModel

    model = TextEmbeddingModel.from_pretrained(_MODEL_NAME)
    all_embeddings: List[List[float]] = []

    batch: List[str] = []
    batch_tokens = 0

    def _flush():
        nonlocal batch, batch_tokens
        if not batch:
            return
        all_embeddings.extend(_embed_batch(model, batch, task_type))
        batch = []
        batch_tokens = 0

    for text in texts:
        tokens = _estimate_tokens(text)
        if batch and (len(batch) >= _MAX_BATCH_ITEMS or batch_tokens + tokens > _MAX_BATCH_TOKENS):
            _flush()
        batch.append(text)
        batch_tokens += tokens

    _flush()
    return all_embeddings


def embed_query(query: str) -> List[float]:
    return embed_texts([query], task_type="RETRIEVAL_QUERY")[0]
