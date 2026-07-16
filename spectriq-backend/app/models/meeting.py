"""
Meeting model: holds the source file reference, transcript, and the
structured output produced by OpenAI (summary / decisions / action items).
"""
import uuid
from datetime import datetime

from sqlalchemy import Column, String, DateTime, Text, ForeignKey, Float
from sqlalchemy.dialects.postgresql import UUID, JSONB

from app.db import Base


class Meeting(Base):
    __tablename__ = "meetings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)

    title = Column(String, nullable=True)
    original_filename = Column(String, nullable=False)
    audio_path = Column(String, nullable=True)   # path to normalized 16kHz mono WAV
    source_path = Column(String, nullable=False)  # path to original upload

    duration_seconds = Column(Float, nullable=True)

    # status mirrors the associated Job's status for quick reads, but the
    # Job record is the source of truth for pipeline progress/errors.
    status = Column(String, nullable=False, default="queued")  # queued|extracting|transcribing|summarizing|done|failed

    # Transcript stored as a list of {start, end, text} segments (JSONB) plus
    # a flattened full-text version for convenience/search.
    transcript_segments = Column(JSONB, nullable=True)
    transcript_text = Column(Text, nullable=True)

    summary = Column(Text, nullable=True)
    key_decisions = Column(JSONB, nullable=True)     # list[str]
    action_items = Column(JSONB, nullable=True)       # list[{text, assignee}]
    open_questions = Column(JSONB, nullable=True)     # list[str]

    error_message = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
