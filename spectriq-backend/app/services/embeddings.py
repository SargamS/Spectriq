"""
Embeddings via the Gemini API (gemini-embedding-001 by default).

Google's Gemini API offers a genuine free tier for both text generation and
embeddings, so this project uses it for the whole "chat with meeting"
pipeline. We use task_type="RETRIEVAL_DOCUMENT" when embedding transcript
chunks for storage, and task_type="RETRIEVAL_QUERY" when embedding an
incoming chat message - Gemini's embedding model is trained to treat these
differently and this measurably improves retrieval quality.
"""
from google import genai
from google.genai import types

from app.config import settings

# Gemini's embed_content endpoint accepts a batch of texts per request; keep
# batches well under the per-request limits so a long transcript doesn't
# trip request-size errors.
BATCH_SIZE = 100


class EmbeddingError(Exception):
    pass


def _client() -> genai.Client:
    if not settings.GEMINI_API_KEY:
        raise EmbeddingError("GEMINI_API_KEY is not configured")
    return genai.Client(api_key=settings.GEMINI_API_KEY)


def embed_documents(texts: list[str]) -> list[list[float]]:
    """
    Embeds a list of transcript chunks for storage. Batches requests so a
    meeting with many chunks doesn't send one huge request (or hundreds of
    tiny ones).
    """
    if not texts:
        return []

    client = _client()
    all_embeddings: list[list[float]] = []

    for i in range(0, len(texts), BATCH_SIZE):
        batch = texts[i : i + BATCH_SIZE]
        try:
            result = client.models.embed_content(
                model=settings.GEMINI_EMBEDDING_MODEL,
                contents=batch,
                config=types.EmbedContentConfig(
                    task_type="RETRIEVAL_DOCUMENT",
                    output_dimensionality=settings.GEMINI_EMBEDDING_DIM,
                ),
            )
        except Exception as exc:  # google-genai raises various exception subtypes
            raise EmbeddingError(f"Gemini embedding request failed: {exc}") from exc

        batch_embeddings = [e.values for e in (result.embeddings or [])]
        if len(batch_embeddings) != len(batch):
            raise EmbeddingError(
                f"Gemini returned {len(batch_embeddings)} embeddings for "
                f"a batch of {len(batch)} texts"
            )

        all_embeddings.extend(batch_embeddings)

    return all_embeddings


def embed_query(text: str) -> list[float]:
    """Embeds a single incoming chat message for similarity search."""
    if not text or not text.strip():
        raise EmbeddingError("Cannot embed an empty query")

    client = _client()
    try:
        result = client.models.embed_content(
            model=settings.GEMINI_EMBEDDING_MODEL,
            contents=[text],
            config=types.EmbedContentConfig(
                task_type="RETRIEVAL_QUERY",
                output_dimensionality=settings.GEMINI_EMBEDDING_DIM,
            ),
        )
    except Exception as exc:
        raise EmbeddingError(f"Gemini embedding request failed: {exc}") from exc

    if not result.embeddings:
        raise EmbeddingError("Gemini returned no embedding for the query")

    return result.embeddings[0].values
