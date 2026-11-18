"""Authorization for Telegram bot users.

Two kinds of right, checked separately:

- `can(role_id, permission)` — role-wide abilities from the permission catalog
  (`monitoring`, `manage_users`, `manage_devices`, `view_logs`).
- `can_device(role_id, device_id, action)` — per-device rights from
  `role_device_access`, with `on` and `off` independent of each other.

Anything unknown is denied. A role that does not exist, a device with no row, or
an action name nobody defined all return False rather than raising: this runs on
the bot's message path, where an exception would drop the reply entirely.
"""

from __future__ import annotations

from collections.abc import Collection

from ..storage.repos import role_devices, roles

BOT_PERMISSIONS: tuple[str, ...] = ("monitoring", "manage_users", "manage_devices", "view_logs")

# action -> column in role_device_access
_ACTION_COLUMNS = {"view": "can_view", "on": "can_on", "off": "can_off"}


def _permissions(role: dict | None) -> Collection[str]:
    if not role:
        return ()
    return role.get("permissions") or ()


def can(role_id: int | None, permission: str) -> bool:
    if role_id is None:
        return False
    return permission in _permissions(roles.get(role_id))


def can_device(role_id: int | None, device_id: int, action: str) -> bool:
    column = _ACTION_COLUMNS.get(action)
    if role_id is None or column is None:
        return False
    row = role_devices.access(role_id, device_id)
    if row is None:
        return False
    return bool(row[column])


def allowed_devices(role_id: int | None) -> list[dict]:
    """Devices the role may at least see, each carrying its own rights."""
    if role_id is None:
        return []
    from ..storage.repos import devices as devices_repo

    by_id = {device["id"]: device for device in devices_repo.list_all()}
    result = []
    for entry in role_devices.get_for_role(role_id):
        device = by_id.get(entry["device_id"])
        if device is None or not entry["can_view"]:
            continue
        result.append({**device, "access": entry})
    return result
