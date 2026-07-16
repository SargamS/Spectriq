"""
Pydantic request/response schemas for the API layer.
"""
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


# ---------- Upload ----------

class UploadResponse(BaseModel):
    meeting_id: UUID
    job_id: UUID


# ---------- Jobs ----------

class JobStatusResponse(BaseModel):
    job_id: UUID
    meeting_id: UUID
    status: str  # queued|extracting|transcribing|summarizing|indexing|done|failed
    error_message: Optional[str] = None
    updated_at: datetime

    class Config:
        from_attributes = True


# ---------- Meetings ----------

class ActionItem(BaseModel):
    text: str
    assignee: Optional[str] = None


class MeetingSummary(BaseModel):
    """Lightweight representation used in list views."""
    id: UUID
    title: Optional[str]
    status: str
    created_at: datetime
    duration_seconds: Optional[float] = None

    class Config:
        from_attributes = True


class TranscriptSegment(BaseModel):
    start: float
    end: float
    text: str


class MeetingDetail(BaseModel):
    """Full representation returned by GET /meetings/{id}."""
    id: UUID
    title: Optional[str]
    status: str
    original_filename: str
    duration_seconds: Optional[float] = None

    transcript_segments: Optional[list[TranscriptSegment]] = None
    transcript_text: Optional[str] = None

    summary: Optional[str] = None
    key_decisions: Optional[list[str]] = None
    action_items: Optional[list[ActionItem]] = None
    open_questions: Optional[list[str]] = None

    error_message: Optional[str] = None

    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class MeetingUpdateRequest(BaseModel):
    """PATCH body - all fields optional, only provided ones are updated."""
    title: Optional[str] = Field(default=None, max_length=300)
    transcript_text: Optional[str] = None


class MeetingListResponse(BaseModel):
    meetings: list[MeetingSummary]


# ---------- Chat (RAG) ----------

class ChatMessage(BaseModel):
    """One turn of prior conversation, as sent by the client."""
    role: str  # "user" | "assistant"
    content: str


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    conversation_history: list[ChatMessage] = Field(default_factory=list)
    # When True, the endpoint returns an SSE stream instead of a single
    # JSON body - see POST /meetings/{id}/chat for details.
    stream: bool = False


class ChatSource(BaseModel):
    """A transcript excerpt the answer was grounded in."""
    chunk_text: str
    start_timestamp: float


class ChatResponse(BaseModel):
    response: str
    sources: list[ChatSource]
