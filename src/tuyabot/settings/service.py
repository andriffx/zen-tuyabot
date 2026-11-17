"""Settings service: cached reads, atomic validated writes, change events."""

from __future__ import annotations

import json
import logging
import threading
from typing import Any

from ..storage import db
from . import registry

logger = logging.getLogger(__name__)

_cache: dict[str, Any] = {}
_cache_lock = threading.Lock()
_cache_loaded = False
_subscribers: list = []


def reset_cache() -> None:
    """Force the next read to reload from the database (used after restore)."""
    global _cache_loaded
    with _cache_lock:
        _cache.clear()
        _cache_loaded = False


def _load_locked() -> None:
    global _cache_loaded
    if _cache_loaded:
        return
    rows: dict[str, Any] = {}
    try:
        with db.connection() as cur:
            cur.execute("SELECT key, value FROM app_settings")
            for row in cur.fetchall():
                if row["key"] in registry.REGISTRY:
                    try:
                        rows[row["key"]] = json.loads(row["value"])
                    except ValueError:
                        logger.warning("Nilai setting rusak diabaikan: %s", row["key"])
    except Exception as exc:  # DB may not be configured yet (early startup)
        logger.debug("Settings belum bisa dibaca: %s", exc)
    _cache.update(rows)
    _cache_loaded = True


def _values() -> dict[str, Any]:
    with _cache_lock:
        _load_locked()
        return dict(_cache)


def get(key: str, default: Any = None) -> Any:
    definition = registry.get(key)
    values = _values()
    return values.get(key, definition.default if default is None else default)


def get_bool(key: str) -> bool:
    return bool(get(key))


def get_int(key: str) -> int:
    return int(get(key))


def get_float(key: str) -> float:
    return float(get(key))


def all_values(*, include_secrets: bool = False) -> dict[str, Any]:
    """Stored values with registry defaults filled in.

    Secrets are never returned as text — only whether a value exists.
    """
    values = _values()
    output: dict[str, Any] = {}
    for definition in registry.DEFS:
        stored = values.get(definition.key, definition.default)
        if definition.secret and not include_secrets:
            output[definition.key] = {"has_value": bool(stored)}
        else:
            output[definition.key] = stored
    return output


def subscribe(callback) -> None:
    """Register a callback receiving {key: new_value} after a successful patch."""
    _subscribers.append(callback)


def patch(items: dict[str, Any], actor: dict[str, Any] | None = None) -> dict[str, Any]:
    """Validate everything first, then write all rows in one transaction.

    Returns the changed map (old → new) for auditing and event dispatch.
    """
    if not items:
        return {}

    validated: dict[str, Any] = {}
    for key, value in items.items():
        definition = registry.get(key)
        if definition.read_only:
            raise registry.ValidationError(key, "setting ini hanya-baca")
        validated[key] = registry.validate(key, value)

    previous = _values()
    changed: dict[str, dict[str, Any]] = {}
    for key, value in validated.items():
        if previous.get(key) != value:
            changed[key] = {"old": previous.get(key), "new": value}

    if not changed:
        return {}

    actor_id = int(actor["id"]) if actor and actor.get("id") else None
    with db.connection(immediate=True) as cur:
        for key, value in validated.items():
            cur.execute(
                """
                INSERT INTO app_settings (key, value, updated_at, updated_by)
                VALUES (?, ?, datetime('now','localtime'), ?)
                ON CONFLICT(key) DO UPDATE SET
                    value = excluded.value,
                    updated_at = excluded.updated_at,
                    updated_by = excluded.updated_by
                """,
                (key, json.dumps(value), actor_id),
            )

    with _cache_lock:
        _cache.update(validated)

    notify = {key: entry["new"] for key, entry in changed.items()}
    for callback in list(_subscribers):
        try:
            callback(notify)
        except Exception:
            logger.exception("Subscriber settings gagal")
    return changed


def schema() -> list[dict[str, Any]]:
    return registry.public_schema()
