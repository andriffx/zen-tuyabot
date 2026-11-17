"""Maintenance mode: application state persisted in app_state, not a setting."""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Any

from ..storage import db
from . import state


def _write(value: dict[str, Any]) -> None:
    with db.connection(immediate=True) as cur:
        cur.execute(
            "INSERT INTO app_state (key, value) VALUES ('maintenance', ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (json.dumps(value),),
        )


def is_on() -> bool:
    current = state.get_state()
    if not current.get("on"):
        return False
    auto_off = current.get("auto_off_at")
    if auto_off and datetime.strptime(auto_off, "%Y-%m-%d %H:%M:%S") <= datetime.now():
        disable()
        return False
    return True


def current() -> dict[str, Any]:
    return state.get_state()


def enable(reason: str | None = None, auto_off_minutes: int | None = None) -> dict[str, Any]:
    value: dict[str, Any] = {"on": True, "reason": reason, "auto_off_at": None}
    if auto_off_minutes:
        value["auto_off_at"] = (datetime.now() + timedelta(minutes=auto_off_minutes)).strftime(
            "%Y-%m-%d %H:%M:%S"
        )
    _write(value)
    return value


def disable() -> dict[str, Any]:
    value = {"on": False, "reason": None, "auto_off_at": None}
    _write(value)
    return value


def block_response() -> tuple[int, dict[str, Any]]:
    return 503, {
        "detail": "maintenance",
        "message": "Sistem sedang dalam pemeliharaan",
        "retry_after": 60,
    }
