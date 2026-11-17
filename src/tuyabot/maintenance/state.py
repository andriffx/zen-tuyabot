"""Session state used by the maintenance gate (Task 8 fills it in fully)."""

from __future__ import annotations

from ..storage import db

CACHE: dict[str, dict] = {}


def get_state() -> dict:
    with db.connection() as cur:
        cur.execute("SELECT value FROM app_state WHERE key = 'maintenance'")
        row = cur.fetchone()
    if row is None:
        return {"on": False, "reason": None, "auto_off_at": None}
    import json

    try:
        return json.loads(row["value"])
    except ValueError:
        return {"on": False, "reason": None, "auto_off_at": None}
