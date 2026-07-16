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
from app.db import get_db
from app.models.meeting import Meeting
from app.models.user import User
from app.schemas import MeetingDetail, MeetingListResponse, MeetingUpdateRequest

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


def _get_owned_meeting_or_404(db: Session, meeting_id: UUID, current_user: User) -> Meeting:
    meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
    if not meeting or meeting.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Meeting not found")
    return meeting
