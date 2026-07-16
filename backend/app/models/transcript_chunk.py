"""
TranscriptChunk model - powers the "chat with meeting" RAG feature.

Each Meeting's transcript is split into overlapping chunks (see
app/services/chunking.py) once summarization finishes. Each chunk stores
its own embedding vector so we can do a similarity search scoped to a
single meeting at chat time.
"""
import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import Column, DateTime, Float, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID

from app.config import settings
from app.db import Base


class TranscriptChunk(Base):
    __tablename__ = "transcript_chunks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    meeting_id = Column(UUID(as_uuid=True), ForeignKey("meetings.id"), nullable=False, index=True)

    chunk_text = Column(Text, nullable=False)
    start_timestamp = Column(Float, nullable=False)  # seconds into the recording
    end_timestamp = Column(Float, nullable=False)

    # faster-whisper doesn't do speaker diarization out of the box, so this
    # stays nullable until/unless a diarization step is added upstream.
    speaker_label = Column(String, nullable=True)

    # Dimension must match GEMINI_EMBEDDING_DIM (the output_dimensionality
    # requested from gemini-embedding-001, 768 by default). If you change
    # the model or dimension, this column needs a migration + a full
    # re-index of existing meetings.
    embedding = Column(Vector(settings.GEMINI_EMBEDDING_DIM), nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        # Approximate nearest-neighbor index for cosine similarity search.
        # `lists` is a reasonable default for small-to-medium datasets; for
        # large deployments, tune it to roughly sqrt(total_rows) and rebuild
        # via a migration (ANALYZE afterwards) rather than relying on this
        # DDL-time default.
        Index(
            "ix_transcript_chunks_embedding_cosine",
            "embedding",
            postgresql_using="ivfflat",
            postgresql_with={"lists": 100},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )
