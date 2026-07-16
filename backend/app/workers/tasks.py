"""
Celery task(s) implementing the meeting-processing pipeline:

    extract audio (ffmpeg) -> transcribe (faster-whisper) -> summarize (OpenAI)
    -> index for chat (chunk + embed via Voyage AI)

Each stage updates the Job's status so the frontend can poll progress via
GET /jobs/{job_id}/status, and each stage is individually wrapped so a
failure anywhere marks the job/meeting as "failed" with a useful message
instead of leaving them stuck "in progress".
"""
import os
import traceback

from app.config import settings
from app.db import SessionLocal
from app.models.job import Job
from app.models.meeting import Meeting
from app.services import audio_extraction, indexing, summarization, transcription
from app.storage import StorageError, delete_local_copy, fetch_local_copy
from app.workers.celery_worker import celery_app

VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".avi", ".webm"}


def _set_stage(db, job: Job, meeting: Meeting, stage: str):
    job.status = stage
    meeting.status = stage
    db.commit()


def _fail(db, job: Job, meeting: Meeting, message: str):
    job.status = "failed"
    job.error_message = message
    meeting.status = "failed"
    meeting.error_message = message
    db.commit()


@celery_app.task(bind=True, name="app.workers.tasks.process_meeting")
def process_meeting(self, meeting_id: str, job_id: str):
    """
    Main pipeline entrypoint, enqueued from POST /upload.
    IDs are passed as strings because Celery serializes task args as JSON.
    """
    db = SessionLocal()
    try:
        job = db.query(Job).filter(Job.id == job_id).first()
        meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()

        if not job or not meeting:
            # Nothing we can update if the records themselves are missing -
            # log and bail rather than raising into Celery's retry machinery.
            return

        job.celery_task_id = self.request.id
        db.commit()

        # ---------- Stage 1: audio extraction ----------
        _set_stage(db, job, meeting, "extracting")
        local_source_path = None
        try:
            # `meeting.source_path` may be a plain local path (STORAGE_BACKEND=local)
            # or an "s3://..." reference (STORAGE_BACKEND=s3). Either way this
            # guarantees a real local file this worker can hand to ffmpeg -
            # downloading it first if the API and worker don't share a disk.
            incoming_dir = os.path.join(settings.STORAGE_DIR, "incoming")
            local_source_path = fetch_local_copy(meeting.source_path, incoming_dir)

            audio_dir = os.path.join(settings.STORAGE_DIR, "audio")
            wav_path = audio_extraction.extract_audio(local_source_path, audio_dir)
            meeting.audio_path = wav_path
            meeting.duration_seconds = audio_extraction.get_duration_seconds(wav_path)
            db.commit()
        except StorageError as exc:
            _fail(db, job, meeting, f"Could not access uploaded file: {exc}")
            return
        except audio_extraction.AudioExtractionError as exc:
            _fail(db, job, meeting, f"Audio extraction failed: {exc}")
            return
        except Exception as exc:
            _fail(db, job, meeting, f"Unexpected error during audio extraction: {exc}")
            return
        finally:
            # Only remove the temp copy if we actually downloaded one (s3
            # backend) - never delete the original when STORAGE_BACKEND=local,
            # since in that case local_source_path *is* the permanent file.
            if settings.STORAGE_BACKEND == "s3" and local_source_path:
                delete_local_copy(local_source_path)

        # ---------- Stage 2: transcription ----------
        _set_stage(db, job, meeting, "transcribing")
        try:
            result = transcription.transcribe(wav_path)
            meeting.transcript_segments = result["segments"]
            meeting.transcript_text = result["full_text"]
            db.commit()
        except transcription.TranscriptionError as exc:
            _fail(db, job, meeting, f"Transcription failed: {exc}")
            return
        except Exception as exc:
            _fail(db, job, meeting, f"Unexpected error during transcription: {exc}")
            return

        # ---------- Stage 3: summarization ----------
        _set_stage(db, job, meeting, "summarizing")
        try:
            structured = summarization.summarize(meeting.transcript_text)
            meeting.title = structured["meeting_title"]
            meeting.summary = structured["summary"]
            meeting.key_decisions = structured["key_decisions"]
            meeting.action_items = structured["action_items"]
            meeting.open_questions = structured["open_questions"]
            db.commit()
        except summarization.SummarizationError as exc:
            _fail(db, job, meeting, f"Summarization failed: {exc}")
            return
        except Exception as exc:
            _fail(db, job, meeting, f"Unexpected error during summarization: {exc}")
            return

        # ---------- Stage 4: indexing (chunk + embed for "chat with meeting") ----------
        _set_stage(db, job, meeting, "indexing")
        try:
            indexing.index_meeting(db, meeting)
        except indexing.IndexingError as exc:
            _fail(db, job, meeting, f"Indexing failed: {exc}")
            return
        except Exception as exc:
            _fail(db, job, meeting, f"Unexpected error during indexing: {exc}")
            return

        # ---------- Done ----------
        job.status = "done"
        meeting.status = "done"
        db.commit()

    except Exception:
        # Catch-all safety net so an unexpected bug never leaves a job
        # silently stuck - always surface *something* to the frontend.
        db.rollback()
        try:
            job = db.query(Job).filter(Job.id == job_id).first()
            meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
            if job and meeting:
                _fail(db, job, meeting, f"Unhandled pipeline error: {traceback.format_exc()[-2000:]}")
        finally:
            pass
    finally:
        db.close()


def is_video_file(filename: str) -> bool:
    return os.path.splitext(filename)[1].lower() in VIDEO_EXTENSIONS
