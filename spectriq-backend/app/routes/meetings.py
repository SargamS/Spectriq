"""
Meeting CRUD-ish endpoints:
  GET   /meetings              - list current user's meetings
  GET   /meetings/{id}         - full meeting detail (transcript/summary/etc.)
  PATCH /meetings/{id}         - edit title or correct the transcript
"""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.background import run_in_background
from app.db import get_db
from app.models.job import Job
from app.models.meeting import Meeting
from app.models.user import User
from app.schemas import MeetingDetail, MeetingListResponse, MeetingUpdateRequest, UploadResponse
from app.workers.tasks import process_meeting

router = APIRouter(prefix="/meetings", tags=["meetings"])


@router.get("", response_model=MeetingListResponse)
def list_meetings(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    meetings = (
        db.query(Meeting)
        .filter(Meeting.user_id == current_user.id)
        .order_by(Meeting.created_at.desc())
        .all()
    )
    return MeetingListResponse(meetings=meetings)


@router.get("/{meeting_id}", response_model=MeetingDetail)
def get_meeting(
    meeting_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    meeting = _get_owned_meeting_or_404(db, meeting_id, current_user)
    return meeting


@router.patch("/{meeting_id}", response_model=MeetingDetail)
def update_meeting(
    meeting_id: UUID,
    payload: MeetingUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    meeting = _get_owned_meeting_or_404(db, meeting_id, current_user)

    if payload.title is not None:
        meeting.title = payload.title
    if payload.transcript_text is not None:
        meeting.transcript_text = payload.transcript_text

    db.commit()
    db.refresh(meeting)
    return meeting


@router.post("/{meeting_id}/retry", response_model=UploadResponse)
def retry_meeting(
    meeting_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Re-runs the processing pipeline for a meeting that failed (e.g. Whisper
    hung/crashed, or OpenAI summarization failed due to a billing/quota
    issue). Only makes sense for a meeting currently in "failed" status.

    This reuses the *same* meeting/job records rather than creating new
    ones, and process_meeting() (see app/workers/tasks.py) skips stages
    whose output already exists on the meeting - so if extraction and
    transcription already succeeded and only summarization failed, retrying
    won't redo the expensive Whisper pass, just the failed step onward.
    """
    meeting = _get_owned_meeting_or_404(db, meeting_id, current_user)

    if meeting.status != "failed":
        raise HTTPException(
            status_code=400,
            detail=f"Meeting is not in a failed state (current status: '{meeting.status}')",
        )

    job = db.query(Job).filter(Job.meeting_id == meeting.id).order_by(Job.created_at.desc()).first()
    if not job:
        raise HTTPException(status_code=404, detail="No job found for this meeting")

    meeting.status = "queued"
    meeting.error_message = None
    job.status = "queued"
    job.error_message = None
    db.commit()
    db.refresh(meeting)
    db.refresh(job)

    run_in_background(process_meeting, str(meeting.id), str(job.id))

    return UploadResponse(meeting_id=meeting.id, job_id=job.id)


def _get_owned_meeting_or_404(db: Session, meeting_id: UUID, current_user: User) -> Meeting:
    meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
    if not meeting or meeting.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Meeting not found")
    return meeting
