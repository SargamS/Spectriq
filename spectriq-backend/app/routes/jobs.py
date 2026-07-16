"""
GET /jobs/{job_id}/status - lets the frontend poll pipeline progress.
"""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.db import get_db
from app.models.job import Job
from app.models.meeting import Meeting
from app.models.user import User
from app.schemas import JobStatusResponse

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("/{job_id}/status", response_model=JobStatusResponse)
def get_job_status(
    job_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Ownership check: only the meeting's owner can poll its job status.
    meeting = db.query(Meeting).filter(Meeting.id == job.meeting_id).first()
    if not meeting or meeting.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Job not found")

    return JobStatusResponse(
        job_id=job.id,
        meeting_id=job.meeting_id,
        status=job.status,
        error_message=job.error_message,
        updated_at=job.updated_at,
    )
