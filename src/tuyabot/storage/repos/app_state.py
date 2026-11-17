"""app_state: small persistent key/value for runtime flags."""

from __future__ import annotations

import json
from typing import Any

from .. import db

_cache: dict[str, Any] = {}


def get(key: str, default: Any = None) -> Any:
    if key in _cache:
        return _cache[key]
    with db.connection() as cur:
        cur.execute("SELECT value FROM app_state WHERE key = ?", (key,))
        row = cur.fetchone()
    if row is None:
        return default
    try:
        value = json.loads(row["value"])
    except ValueError:
        return default
    _cache[key] = value
    return value


def set(key: str, value: Any) -> None:
    with db.connection(immediate=True) as cur:
        cur.execute(
            "INSERT INTO app_state (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, json.dumps(value)),
        )
    _cache[key] = value


def reset_cache() -> None:
    _cache.clear()


def is_setup_complete() -> bool:
    return bool(get("setup_complete", False))
