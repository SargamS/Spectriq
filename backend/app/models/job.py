"""
Job model: tracks background pipeline progress for a Meeting so the
frontend can poll GET /jobs/{job_id}/status.
"""
import uuid
from datetime import datetime

from sqlalchemy import Column, String, DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID

from app.db import Base


class Job(Base):
    __tablename__ = "jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    meeting_id = Column(UUID(as_uuid=True), ForeignKey("meetings.id"), nullable=False, index=True)

    # queued -> extracting -> transcribing -> summarizing -> indexing -> done
    #                                                                \-> failed
    # "indexing" covers chunking + embedding the transcript for the
    # "chat with meeting" RAG feature (see app/services/chunking.py and
    # app/services/embeddings.py). Chat is only available once a meeting
    # reaches "done".
    status = Column(String, nullable=False, default="queued")
    error_message = Column(Text, nullable=True)

    celery_task_id = Column(String, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
