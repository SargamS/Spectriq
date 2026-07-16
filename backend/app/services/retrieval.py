"""
Vector similarity search over a single meeting's TranscriptChunk rows.

Uses pgvector's cosine distance operator (`<=>`, exposed via the
`cosine_distance()` comparator that pgvector's SQLAlchemy integration adds
to Vector columns) to find the chunks most relevant to a chat query.
"""
from uuid import UUID

from sqlalchemy.orm import Session

from app.config import settings
from app.models.transcript_chunk import TranscriptChunk


class RetrievalError(Exception):
    pass


def retrieve_relevant_chunks(
    db: Session,
    meeting_id: UUID,
    query_embedding: list[float],
    top_k: int = None,
) -> list[TranscriptChunk]:
    """
    Returns the top_k TranscriptChunks for `meeting_id` most similar to
    `query_embedding`, ordered by cosine distance (closest first).
    """
    top_k = top_k or settings.CHAT_TOP_K_CHUNKS

    if not query_embedding:
        raise RetrievalError("query_embedding is empty")

    try:
        chunks = (
            db.query(TranscriptChunk)
            .filter(TranscriptChunk.meeting_id == meeting_id)
            .order_by(TranscriptChunk.embedding.cosine_distance(query_embedding))
            .limit(top_k)
            .all()
        )
    except Exception as exc:
        raise RetrievalError(f"Vector similarity query failed: {exc}") from exc

    return chunks
