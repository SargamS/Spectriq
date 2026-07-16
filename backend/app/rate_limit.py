"""
Simple Redis-backed fixed-window rate limiter.

Used to cap chat requests per meeting (each call embeds a query via Voyage
AND calls Claude, so this is mainly a cost-control guard rail rather than
an anti-abuse measure).
"""
from functools import lru_cache

import redis

from app.config import settings


@lru_cache
def _redis_client() -> redis.Redis:
    # Reuses the same Redis instance Celery already talks to; a separate
    # DB index isn't necessary since keys are namespaced below.
    return redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)


class RateLimitExceeded(Exception):
    def __init__(self, retry_after_seconds: int):
        self.retry_after_seconds = retry_after_seconds
        super().__init__(f"Rate limit exceeded, retry after {retry_after_seconds}s")


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
    key = f"chat_rate_limit:{meeting_id}"

    try:
        client = _redis_client()
        current = client.incr(key)
        if current == 1:
            client.expire(key, 3600)  # start a fresh 1-hour window

        if current > limit_per_hour:
            ttl = client.ttl(key)
            raise RateLimitExceeded(retry_after_seconds=max(ttl, 1))
    except redis.RedisError as exc:
        # If Redis itself is unavailable, fail open rather than blocking
        # chat entirely - but this should be alerted on in production.
        import logging

        logging.getLogger(__name__).warning("Rate limit check failed, failing open: %s", exc)
