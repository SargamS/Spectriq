"""
POST /meetings/{meeting_id}/chat - "chat with meeting" RAG endpoint.

Pipeline per request:
  1. embed the user's message (Gemini)
  2. pgvector similarity search over that meeting's TranscriptChunks
  3. build a grounded prompt (retrieved chunks + conversation history)
  4. call Gemini, streaming the answer via SSE if the client asked for it
  5. return the answer plus the source chunks it was grounded in
"""
import json
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.db import get_db
from app.models.meeting import Meeting
from app.models.user import User
from app.rate_limit import RateLimitExceeded, check_and_increment_chat_rate_limit
from app.schemas import ChatRequest, ChatResponse, ChatSource
from app.services import chat_completion, embeddings, retrieval

router = APIRouter(prefix="/meetings", tags=["chat"])

# Job/meeting statuses reached before indexing has finished - chat isn't
# available yet if the meeting is in one of these.
IN_PROGRESS_STATUSES = {"queued", "extracting", "transcribing", "summarizing", "indexing"}


def _get_owned_meeting_or_404(db: Session, meeting_id: UUID, current_user: User) -> Meeting:
    meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
    if not meeting or meeting.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Meeting not found")
    return meeting


def _ensure_chat_ready(meeting: Meeting) -> None:
    """Raises a clear, actionable error if the meeting isn't indexed yet."""
    if meeting.status == "done":
        return
    if meeting.status in IN_PROGRESS_STATUSES:
        raise HTTPException(
            status_code=409,
            detail="This meeting is still being processed for chat. Try again shortly.",
        )
    if meeting.status == "failed":
        raise HTTPException(
            status_code=422,
            detail=f"This meeting failed processing and can't be chatted with: "
                   f"{meeting.error_message or 'unknown error'}",
        )
    # Any other unexpected status - fail closed with a generic message.
    raise HTTPException(status_code=409, detail="This meeting is not ready for chat yet.")


@router.post("/{meeting_id}/chat")
def chat_with_meeting(
    meeting_id: UUID,
    payload: ChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    meeting = _get_owned_meeting_or_404(db, meeting_id, current_user)
    _ensure_chat_ready(meeting)

    try:
        check_and_increment_chat_rate_limit(str(meeting.id))
    except RateLimitExceeded as exc:
        raise HTTPException(
            status_code=429,
            detail="Too many chat messages for this meeting. Please wait before sending more.",
            headers={"Retry-After": str(exc.retry_after_seconds)},
        )

    # ---------- 1. Embed the query ----------
    try:
        query_embedding = embeddings.embed_query(payload.message)
    except embeddings.EmbeddingError as exc:
        raise HTTPException(status_code=502, detail=f"Failed to process your message: {exc}")

    # ---------- 2. Retrieve relevant chunks ----------
    try:
        chunks = retrieval.retrieve_relevant_chunks(db, meeting.id, query_embedding)
    except retrieval.RetrievalError as exc:
        raise HTTPException(status_code=500, detail=f"Failed to search this meeting's transcript: {exc}")

    conversation_history = [turn.model_dump() for turn in payload.conversation_history]
    sources = [
        ChatSource(chunk_text=c.chunk_text, start_timestamp=c.start_timestamp) for c in chunks
    ]

    # ---------- 3+4. Generate the answer (streaming or not) ----------
    if payload.stream:
        return StreamingResponse(
            _sse_stream(meeting, chunks, conversation_history, payload.message, sources),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    try:
        answer = chat_completion.generate_answer(
            meeting_title=meeting.title,
            chunks=chunks,
            conversation_history=conversation_history,
            user_message=payload.message,
        )
    except chat_completion.ChatCompletionError as exc:
        raise HTTPException(status_code=502, detail=f"Failed to generate a response: {exc}")

    return ChatResponse(response=answer, sources=sources)


def _sse_stream(meeting, chunks, conversation_history, user_message, sources):
    """
    Yields Server-Sent Events:
      - one "delta" event per text chunk as Claude streams its answer
      - a final "done" event with the full response text + sources
      - an "error" event if generation fails partway through
    """
    full_text_parts: list[str] = []
    try:
        for delta in chat_completion.stream_answer(
            meeting_title=meeting.title,
            chunks=chunks,
            conversation_history=conversation_history,
            user_message=user_message,
        ):
            full_text_parts.append(delta)
            yield f"event: delta\ndata: {json.dumps({'text': delta})}\n\n"

        final_payload = {
            "response": "".join(full_text_parts),
            "sources": [s.model_dump() for s in sources],
        }
        yield f"event: done\ndata: {json.dumps(final_payload)}\n\n"

    except chat_completion.ChatCompletionError as exc:
        yield f"event: error\ndata: {json.dumps({'error': str(exc)})}\n\n"
