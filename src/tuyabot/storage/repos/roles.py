"""Role repository — roles live in the DB, permissions are catalog keys."""

from __future__ import annotations

import json
from typing import Any

from .. import db

SELECT_WITH_COUNTS = """
    SELECT r.id, r.slug, r.name, r.description, r.permissions,
           r.rate_limit_per_minute, r.is_system, r.is_protected,
           (
               SELECT COUNT(*) FROM web_users w WHERE w.role_id = r.id
           ) + (
               SELECT COUNT(*) FROM telegram_users t WHERE t.role_id = r.id
           ) AS user_count
    FROM roles r
"""


def _row_to_dict(row) -> dict[str, Any]:
    data = dict(row)
    data["permissions"] = json.loads(data["permissions"] or "[]")
    return data


def list_all() -> list[dict[str, Any]]:
    with db.connection() as cur:
        cur.execute(SELECT_WITH_COUNTS + " ORDER BY r.id")
        return [_row_to_dict(row) for row in cur.fetchall()]


def get(role_id: int) -> dict[str, Any] | None:
    with db.connection() as cur:
        cur.execute(SELECT_WITH_COUNTS + " WHERE r.id = ?", (role_id,))
        row = cur.fetchone()
        return _row_to_dict(row) if row else None


def get_by_slug(slug: str) -> dict[str, Any] | None:
    with db.connection() as cur:
        cur.execute(SELECT_WITH_COUNTS + " WHERE r.slug = ?", (slug,))
        row = cur.fetchone()
        return _row_to_dict(row) if row else None


def create(slug: str, name: str, description: str | None, permissions: list[str]) -> int:
    with db.connection(immediate=True) as cur:
        cur.execute(
            """
            INSERT INTO roles (slug, name, description, permissions, is_system, is_protected)
            VALUES (?, ?, ?, ?, 0, 0)
            """,
            (slug, name, description, json.dumps(sorted(set(permissions)))),
        )
        return int(cur.lastrowid)


def update(role_id: int, **fields: Any) -> None:
    allowed = {"name", "description", "permissions", "rate_limit_per_minute"}
    updates = {k: v for k, v in fields.items() if k in allowed and v is not None}
    if not updates:
        return
    if "permissions" in updates:
        updates["permissions"] = json.dumps(sorted(set(updates["permissions"])))
    assignments = ", ".join(f"{key} = ?" for key in updates)
    values = [*updates.values(), role_id]
    with db.connection(immediate=True) as cur:
        cur.execute(
            f"UPDATE roles SET {assignments}, updated_at = datetime('now','localtime') WHERE id = ?",
            values,
        )


def delete(role_id: int) -> None:
    with db.connection(immediate=True) as cur:
        cur.execute("DELETE FROM roles WHERE id = ?", (role_id,))


def count_users(role_id: int) -> int:
    role = get(role_id)
    return int(role["user_count"]) if role else 0


def roles_referencing(role_id: int) -> dict[str, int]:
    """Where a role is used, so deletion can refuse with a useful message."""
    with db.connection() as cur:
        cur.execute("SELECT COUNT(*) FROM web_users WHERE role_id = ?", (role_id,))
        web = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM telegram_users WHERE role_id = ?", (role_id,))
        telegram = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM api_keys WHERE role_id = ?", (role_id,))
        keys = cur.fetchone()[0]
        cur.execute(
            "SELECT COUNT(*) FROM devices WHERE EXISTS "
            "(SELECT 1 FROM json_each(devices.access_roles) WHERE json_each.value = ?)",
            (role_id,),
        )
        devices = cur.fetchone()[0]
    return {"web_users": web, "telegram_users": telegram, "api_keys": keys, "devices": devices}
