"""
Embeddings via the Jina AI API (jina-embeddings-v3 by default).

Jina's embed endpoint accepts a "task" field that measurably improves
retrieval quality when set correctly: "retrieval.passage" for the chunks
being stored, "retrieval.query" for an incoming chat message being
searched against them - mirrors what Gemini's task_type did previously.
"""
import requests

from app.config import settings

JINA_EMBEDDINGS_URL = "https://api.jina.ai/v1/embeddings"

# Batch requests so a meeting with many chunks doesn't send one huge
# request (or hundreds of tiny ones).
BATCH_SIZE = 100

REQUEST_TIMEOUT_SECONDS = 60


class EmbeddingError(Exception):
    pass


def _headers() -> dict:
    if not settings.JINA_API_KEY:
        raise EmbeddingError("JINA_API_KEY is not configured")
    return {
        "Authorization": f"Bearer {settings.JINA_API_KEY}",
        "Content-Type": "application/json",
    }


def _embed(texts: list[str], task: str) -> list[list[float]]:
    if not texts:
        return []

    try:
        response = requests.post(
            JINA_EMBEDDINGS_URL,
            headers=_headers(),
            json={
                "model": settings.JINA_EMBEDDING_MODEL,
                "task": task,
                "dimensions": settings.JINA_EMBEDDING_DIM,
                "input": texts,
            },
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise EmbeddingError(f"Jina embedding request failed: {exc}") from exc

    data = response.json().get("data", [])
    if len(data) != len(texts):
        raise EmbeddingError(
            f"Jina returned {len(data)} embeddings for a batch of {len(texts)} texts"
        )

    # Jina returns results tagged with their original index; sort defensively
    # rather than assuming response order matches request order.
    data_sorted = sorted(data, key=lambda item: item.get("index", 0))
    return [item["embedding"] for item in data_sorted]


def embed_documents(texts: list[str]) -> list[list[float]]:
    """Embeds a list of transcript chunks for storage."""
    if not texts:
        return []

    all_embeddings: list[list[float]] = []
    for i in range(0, len(texts), BATCH_SIZE):
        batch = texts[i : i + BATCH_SIZE]
        all_embeddings.extend(_embed(batch, task="retrieval.passage"))
    return all_embeddings


def embed_query(text: str) -> list[float]:
    """Embeds a single incoming chat message for similarity search."""
    if not text or not text.strip():
        raise EmbeddingError("Cannot embed an empty query")

    embeddings = _embed([text], task="retrieval.query")
    if not embeddings:
        raise EmbeddingError("Jina returned no embedding for the query")
    return embeddings[0]
