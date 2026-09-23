"""Soft daily counters for expensive LLM match calls."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

import redis

from ..config import settings

logger = logging.getLogger(__name__)


class MatchBudgetExceeded(Exception):
    """Raised when the daily LLM match call budget is exhausted."""

    def __init__(self, used: int, limit: int) -> None:
        self.used = used
        self.limit = limit
        super().__init__(
            f"Daily LLM match budget exceeded ({used}/{limit}). Try again tomorrow."
        )


def _redis_client() -> redis.Redis:
    return redis.Redis.from_url(settings.redis_url, decode_responses=True)


def _day_key(person_id: str) -> str:
    day = datetime.now(UTC).strftime("%Y-%m-%d")
    return f"llm_match_budget:{person_id}:{day}"


def get_match_usage(person_id: str) -> int:
    try:
        raw = _redis_client().get(_day_key(person_id))
        return int(raw or 0)
    except Exception as exc:
        logger.warning("Failed to read match budget from Redis: %s", exc)
        return 0


def reserve_match_calls(person_id: str, count: int) -> int:
    """Atomically reserve ``count`` match LLM calls against the daily limit.

    Returns the new usage total. Raises ``MatchBudgetExceeded`` if the
    reservation would exceed ``settings.llm_match_daily_limit``.
    """
    if count <= 0:
        return get_match_usage(person_id)

    limit = settings.llm_match_daily_limit
    key = _day_key(person_id)
    try:
        client = _redis_client()
        # Optimistic check + incr; roll back on overage.
        current = int(client.get(key) or 0)
        if current + count > limit:
            raise MatchBudgetExceeded(used=current, limit=limit)
        new_total = int(client.incrby(key, count))
        if new_total == count:
            client.expire(key, 60 * 60 * 48)
        if new_total > limit:
            client.decrby(key, count)
            raise MatchBudgetExceeded(used=new_total - count, limit=limit)
        return new_total
    except MatchBudgetExceeded:
        raise
    except Exception as exc:
        # Fail open on Redis outages so matching remains usable in local/dev.
        logger.warning("Match budget Redis unavailable; allowing calls: %s", exc)
        return get_match_usage(person_id) + count
