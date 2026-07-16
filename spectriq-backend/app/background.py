"""
Lightweight in-process background task runner.

This replaces Celery + Redis: instead of enqueueing a job for a separate
worker process (which requires a paid Render service, since Background
Workers have no free tier), the meeting-processing pipeline runs in a
background thread inside the same process as the API. This lets the whole
app run as a single free-tier-friendly web service.

Trade-off worth knowing: free web services on Render spin down after a
period with no incoming HTTP traffic. A long-running transcription job
doesn't itself count as "traffic," so if nothing polls the API for a
while, the platform could spin the instance down mid-job. In practice
this is a non-issue as long as the frontend is open and polling
GET /meetings/{id} every couple seconds while a job is in progress (which
it already does) - that keeps the service alive. If you outgrow this
(e.g. want processing to survive with no one watching), moving back to a
paid Background Worker + Redis is the natural next step.
"""
import logging
import threading

logger = logging.getLogger(__name__)

# A small fixed pool rather than one thread per upload, so a burst of
# uploads can't spawn unbounded threads and exhaust memory/CPU on a small
# free-tier instance. Whisper transcription is CPU-bound and slow, so
# only a couple should run concurrently anyway.
_MAX_CONCURRENT_JOBS = 2
_semaphore = threading.Semaphore(_MAX_CONCURRENT_JOBS)


def _run(fn, args):
    with _semaphore:
        try:
            fn(*args)
        except Exception:
            # The pipeline function already catches and records its own
            # failures against the Job/Meeting rows; this is just a last
            # resort so a truly unexpected bug doesn't crash the thread
            # silently with no trace anywhere.
            logger.exception("Unhandled error in background task %s", fn)


def run_in_background(fn, *args) -> None:
    """Fire-and-forget: runs fn(*args) on a daemon thread and returns immediately."""
    thread = threading.Thread(target=_run, args=(fn, args), daemon=True)
    thread.start()
