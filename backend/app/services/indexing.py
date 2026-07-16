"""
Ties chunking + embedding + persistence together into a single
"index this meeting for chat" operation, called from the Celery pipeline's
indexing stage.
"""
from sqlalchemy.orm import Session

from app.models.meeting import Meeting
from app.models.transcript_chunk import TranscriptChunk
from app.services import chunking, embeddings


class IndexingError(Exception):
    pass


def index_meeting(db: Session, meeting: Meeting) -> int:
    """
    Chunks `meeting.transcript_segments`, embeds each chunk via Voyage AI,
    and persists TranscriptChunk rows. Returns the number of chunks
    created. Any existing chunks for the meeting are cleared first, so
    this is safe to re-run (e.g. after a transcript correction).
    """
    if not meeting.transcript_segments:
        raise IndexingError("Meeting has no transcript segments to index")

    chunk_data = chunking.chunk_transcript(meeting.transcript_segments)
    if not chunk_data:
        raise IndexingError("Chunking produced no chunks from the transcript")

    try:
        vectors = embeddings.embed_documents([c.chunk_text for c in chunk_data])
    except embeddings.EmbeddingError as exc:
        raise IndexingError(f"Embedding failed: {exc}") from exc

    if len(vectors) != len(chunk_data):
        raise IndexingError(
            f"Embedding count mismatch: {len(vectors)} vectors for {len(chunk_data)} chunks"
        )

    # Clear any prior chunks (e.g. from a re-run) before inserting fresh ones.
    db.query(TranscriptChunk).filter(TranscriptChunk.meeting_id == meeting.id).delete()

    rows = [
        TranscriptChunk(
            meeting_id=meeting.id,
            chunk_text=data.chunk_text,
            start_timestamp=data.start_timestamp,
            end_timestamp=data.end_timestamp,
            speaker_label=data.speaker_label,
            embedding=vector,
        )
        for data, vector in zip(chunk_data, vectors)
    ]
    db.bulk_save_objects(rows)
    db.commit()

    return len(rows)
