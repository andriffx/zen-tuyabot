"""In-memory sliding-window rate limiting and login attempt counters."""

from __future__ import annotations

import threading
import time

_lock = threading.Lock()
_buckets: dict[str, list[float]] = {}


def allow(key: str, limit: int, window_seconds: int) -> bool:
    """Return True when the caller is under the limit; records the hit."""
    now = time.monotonic()
    cutoff = now - window_seconds
    with _lock:
        hits = [stamp for stamp in _buckets.get(key, []) if stamp > cutoff]
        if len(hits) >= limit:
            _buckets[key] = hits
            return False
        hits.append(now)
        _buckets[key] = hits
        return True


def retry_after(key: str, window_seconds: int) -> int:
    now = time.monotonic()
    with _lock:
        hits = _buckets.get(key, [])
        if not hits:
            return 0
        return max(1, int(window_seconds - (now - min(hits))))


def reset(key: str | None = None) -> None:
    with _lock:
        if key is None:
            _buckets.clear()
        else:
            _buckets.pop(key, None)


def prune(window_seconds: int) -> int:
    """Drop idle buckets so the dict cannot grow without bound."""
    cutoff = time.monotonic() - window_seconds
    removed = 0
    with _lock:
        for key in list(_buckets):
            kept = [stamp for stamp in _buckets[key] if stamp > cutoff]
            if kept:
                _buckets[key] = kept
            else:
                del _buckets[key]
                removed += 1
    return removed
