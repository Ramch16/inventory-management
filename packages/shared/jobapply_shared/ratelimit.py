"""Rate limiting.

Two implementations behind one protocol: an in-memory limiter for tests and single
process development, and a Redis limiter for anything multi-process.

These limits exist to protect the *user* from runaway automation and from account
problems. They are never used to work around an employer's own limits.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class RateLimitDecision:
    allowed: bool
    remaining: int
    retry_after_seconds: int


class RateLimiter(Protocol):
    def check(self, key: str, limit: int, window_seconds: int) -> RateLimitDecision: ...


class InMemoryRateLimiter:
    """Fixed-window counter. Adequate for tests and single-process development."""

    def __init__(self) -> None:
        self._buckets: dict[str, list[float]] = {}
        self._lock = threading.Lock()

    def check(self, key: str, limit: int, window_seconds: int) -> RateLimitDecision:
        now = time.time()
        cutoff = now - window_seconds
        with self._lock:
            hits = [stamp for stamp in self._buckets.get(key, []) if stamp > cutoff]
            if len(hits) >= limit:
                retry_after = int(hits[0] + window_seconds - now) + 1
                self._buckets[key] = hits
                return RateLimitDecision(False, 0, max(retry_after, 1))
            hits.append(now)
            self._buckets[key] = hits
            return RateLimitDecision(True, max(limit - len(hits), 0), 0)

    def reset(self, key: str | None = None) -> None:
        with self._lock:
            if key is None:
                self._buckets.clear()
            else:
                self._buckets.pop(key, None)


class RedisRateLimiter:
    """Sliding-window counter backed by a Redis sorted set."""

    def __init__(self, client: object) -> None:
        self._client = client

    def check(self, key: str, limit: int, window_seconds: int) -> RateLimitDecision:
        import uuid

        now = time.time()
        cutoff = now - window_seconds
        redis_key = f"ratelimit:{key}"
        pipe = self._client.pipeline()  # type: ignore[attr-defined]
        pipe.zremrangebyscore(redis_key, 0, cutoff)
        pipe.zcard(redis_key)
        pipe.zadd(redis_key, {uuid.uuid4().hex: now})
        pipe.expire(redis_key, window_seconds + 1)
        _, count, _, _ = pipe.execute()
        if count >= limit:
            self._client.zpopmax(redis_key)  # type: ignore[attr-defined]
            oldest = self._client.zrange(redis_key, 0, 0, withscores=True)  # type: ignore[attr-defined]
            retry_after = int(oldest[0][1] + window_seconds - now) + 1 if oldest else window_seconds
            return RateLimitDecision(False, 0, max(retry_after, 1))
        return RateLimitDecision(True, max(limit - count - 1, 0), 0)
