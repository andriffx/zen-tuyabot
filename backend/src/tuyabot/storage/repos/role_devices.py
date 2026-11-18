"""Per-device access per role.

One row per (role, device) pair. `can_view`, `can_on` and `can_off` are separate
because a role may be allowed to switch a device on but not off — the reference
behaviour for the pump — and because seeing a status is not the same as sending
a command.

This table is the only authorization source for device access. The legacy
`devices.access_roles` column is deprecated and exists only so migration 0005
could backfill it.
"""

from __future__ import annotations

from typing import Any

from .. import db


def get_for_role(role_id: int) -> list[dict[str, Any]]:
    with db.connection() as cur:
        cur.execute(
            "SELECT device_id, can_view, can_on, can_off "
            "FROM role_device_access WHERE role_id = ? ORDER BY device_id",
            (role_id,),
        )
        return [
            {
                "device_id": row["device_id"],
                "can_view": bool(row["can_view"]),
                "can_on": bool(row["can_on"]),
                "can_off": bool(row["can_off"]),
            }
            for row in cur.fetchall()
        ]


def access(role_id: int, device_id: int) -> dict[str, Any] | None:
    with db.connection() as cur:
        cur.execute(
            "SELECT can_view, can_on, can_off FROM role_device_access "
            "WHERE role_id = ? AND device_id = ?",
            (role_id, device_id),
        )
        row = cur.fetchone()
        if row is None:
            return None
        return {
            "can_view": bool(row["can_view"]),
            "can_on": bool(row["can_on"]),
            "can_off": bool(row["can_off"]),
        }


def set_for_role(role_id: int, entries: list[dict[str, Any]]) -> None:
    """Replace the role's whole matrix in one transaction.

    Replace rather than merge: the UI sends what the operator sees, and a
    device removed from the table must stop being reachable.
    """
    with db.connection(immediate=True) as cur:
        cur.execute("DELETE FROM role_device_access WHERE role_id = ?", (role_id,))
        cur.executemany(
            "INSERT INTO role_device_access (role_id, device_id, can_view, can_on, can_off) "
            "VALUES (?, ?, ?, ?, ?)",
            [
                (
                    role_id,
                    int(entry["device_id"]),
                    int(bool(entry.get("can_view"))),
                    int(bool(entry.get("can_on"))),
                    int(bool(entry.get("can_off"))),
                )
                for entry in entries
            ],
        )
