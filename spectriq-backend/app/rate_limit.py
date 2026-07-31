"""
Simple in-process fixed-window rate limiter.

Used to cap chat requests per meeting (each call embeds a query AND calls
Gemini's chat model, so this is mainly a cost-control guard rail rather
than an anti-abuse measure).

This used to be Redis-backed so multiple worker processes could share
counters. Now that the whole app runs as a single process (see
app/background.py for why), an in-memory dict + lock is simpler and needs
no extra service. The one trade-off: counters reset if the process
restarts (e.g. a free-tier spin-down/spin-up cycle) - acceptable for a
cost guard rail, not something you'd want for a real anti-abuse limiter.
"""
import threading
import time

from app.config import settings


class RateLimitExceeded(Exception):
    def __init__(self, retry_after_seconds: int):
        self.retry_after_seconds = retry_after_seconds
        super().__init__(f"Rate limit exceeded, retry after {retry_after_seconds}s")


_lock = threading.Lock()
# meeting_id -> (window_start_epoch_seconds, count)
_counters: dict[str, tuple[float, int]] = {}

_WINDOW_SECONDS = 3600


def check_and_increment_chat_rate_limit(meeting_id: str, limit_per_hour: int = None) -> None:
    """
    Fixed one-hour window counter keyed by meeting_id. Raises
    RateLimitExceeded if the meeting has already hit `limit_per_hour`
    chat messages within the current window.

    Fixed windows are simpler than sliding windows and good enough for a
    cost-control guard rail; a burst right at the window boundary is an
    acceptable tradeoff here.
    """
    limit_per_hour = limit_per_hour or settings.CHAT_RATE_LIMIT_PER_HOUR
    now = time.time()

    with _lock:
        window_start, count = _counters.get(meeting_id, (now, 0))

        if now - window_start >= _WINDOW_SECONDS:
            # Window expired - start a fresh one.
            window_start, count = now, 0

        count += 1
        _counters[meeting_id] = (window_start, count)

        if count > limit_per_hour:
            retry_after = max(int(_WINDOW_SECONDS - (now - window_start)), 1)
            raise RateLimitExceeded(retry_after_seconds=retry_after)
