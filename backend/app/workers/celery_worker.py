"""
Celery application instance. Run the worker with:

    celery -A app.workers.celery_worker worker --loglevel=info

Redis is used as both broker and result backend.
"""
from celery import Celery

from app.config import settings

celery_app = Celery(
    "spectriq",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["app.workers.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    # Long-running tasks (transcription of long meetings) shouldn't be
    # silently killed by a short default visibility timeout.
    broker_transport_options={"visibility_timeout": 3600},
    task_acks_late=True,       # re-deliver if a worker dies mid-task
    worker_prefetch_multiplier=1,
)
