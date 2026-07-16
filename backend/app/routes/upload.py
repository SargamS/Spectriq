"""
POST /upload - accepts an audio/video file, persists it, creates the
Meeting + Job records, and enqueues the background processing pipeline.
"""
import os

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.config import settings
from app.db import get_db
from app.models.job import Job
from app.models.meeting import Meeting
from app.models.user import User
from app.schemas import UploadResponse
from app.storage import save_upload
from app.workers.tasks import process_meeting

router = APIRouter(tags=["upload"])

ALLOWED_CONTENT_TYPES = {
    # audio
    "audio/mpeg", "audio/mp3", "audio/wav", "audio/x-wav", "audio/mp4",
    "audio/webm", "audio/ogg", "audio/x-m4a", "audio/aac",
    # video
    "video/mp4", "video/quicktime", "video/x-matroska", "video/webm", "video/x-msvideo",
}

ALLOWED_EXTENSIONS = {
    ".mp3", ".wav", ".m4a", ".aac", ".ogg", ".webm",
    ".mp4", ".mov", ".mkv", ".avi",
}


def _validate_upload(file: UploadFile):
    ext = os.path.splitext(file.filename or "")[1].lower()

    if ext not in ALLOWED_EXTENSIONS and file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported file type '{file.content_type}' ({ext}). "
                   f"Accepted formats: {sorted(ALLOWED_EXTENSIONS)}",
        )


@router.post("/upload", response_model=UploadResponse)
async def upload_meeting(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _validate_upload(file)

    # Enforce size limit by streaming and counting bytes, so we never
    # buffer an oversized file fully into memory before rejecting it.
    max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    total_bytes = 0

    ext = os.path.splitext(file.filename or "")[1].lower() or ".bin"
    tmp_path = os.path.join(settings.STORAGE_DIR, f"_incoming_{os.urandom(8).hex()}{ext}")
    os.makedirs(settings.STORAGE_DIR, exist_ok=True)

    try:
        with open(tmp_path, "wb") as out:
            while chunk := await file.read(1024 * 1024):
                total_bytes += len(chunk)
                if total_bytes > max_bytes:
                    raise HTTPException(
                        status_code=413,
                        detail=f"File exceeds MAX_UPLOAD_SIZE_MB ({settings.MAX_UPLOAD_SIZE_MB} MB)",
                    )
                out.write(chunk)

        # Re-open as a plain file object so storage.save_upload can reuse
        # its normal chunked-copy path (keeps a single, consistent way of
        # persisting files regardless of how they arrived).
        with open(tmp_path, "rb") as f:
            final_path = save_upload(f, file.filename)
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

    meeting = Meeting(
        user_id=current_user.id,
        original_filename=file.filename,
        source_path=final_path,
        status="queued",
    )
    db.add(meeting)
    db.flush()  # populate meeting.id without committing yet

    job = Job(meeting_id=meeting.id, status="queued")
    db.add(job)
    db.commit()
    db.refresh(meeting)
    db.refresh(job)

    # Enqueue the Celery pipeline. IDs are passed as strings (UUID isn't
    # JSON-serializable by default).
    process_meeting.delay(str(meeting.id), str(job.id))

    return UploadResponse(meeting_id=meeting.id, job_id=job.id)
