"""A small in-process rate limiter.

Deliberately simple: a sliding window of timestamps per key. Render runs a single
web instance, so process-local state is sufficient. If the service ever scales
out, swap this for a Redis-backed limiter — the call sites do not change.
"""

from __future__ import annotations

import time
from collections import defaultdict, deque

from fastapi import Request

from app.core.errors import RateLimitedError

_buckets: dict[str, deque[float]] = defaultdict(deque)
_MAX_KEYS = 10_000


def client_key(request: Request, scope: str) -> str:
    forwarded = (request.headers.get("x-forwarded-for") or "").split(",")[0].strip()
    host = forwarded or (request.client.host if request.client else "unknown")
    return f"{scope}:{host}"


def enforce(key: str, *, limit: int, window_seconds: int) -> None:
    if limit <= 0:
        return

    now = time.monotonic()
    bucket = _buckets[key]
    cutoff = now - window_seconds

    while bucket and bucket[0] < cutoff:
        bucket.popleft()

    if len(bucket) >= limit:
        retry_after = int(bucket[0] + window_seconds - now) + 1
        raise RateLimitedError(
            f"Too many requests. Try again in {retry_after}s.",
            code="RATE_LIMITED",
            details={"retry_after": retry_after},
        )

    bucket.append(now)

    if len(_buckets) > _MAX_KEYS:
        _prune(cutoff)


def _prune(cutoff: float) -> None:
    for key in [k for k, v in _buckets.items() if not v or v[-1] < cutoff]:
        _buckets.pop(key, None)


def reset() -> None:
    """Test helper."""
    _buckets.clear()
