"""In-memory device registry, refreshed on every device mutation."""

from __future__ import annotations

import threading
from typing import Any

from ..storage.repos import devices as devices_repo

_lock = threading.Lock()
_snapshot: list[dict[str, Any]] | None = None


def reload() -> list[dict[str, Any]]:
    global _snapshot
    devices = devices_repo.list_all(active_only=True)
    with _lock:
        _snapshot = devices
    return devices


def _current() -> list[dict[str, Any]]:
    global _snapshot
    with _lock:
        current = _snapshot
    if current is None:
        return reload()
    return current


def reset_cache() -> None:
    """Drop the snapshot (used after a DB restore)."""
    global _snapshot
    with _lock:
        _snapshot = None


def all_devices() -> list[dict[str, Any]]:
    return list(_current())


def visible_to(principal) -> list[dict[str, Any]]:
    """Devices this principal may see."""
    return [device for device in _current() if can_view(principal, device)]


def get(device_id: int) -> dict[str, Any] | None:
    for device in _current():
        if device["id"] == device_id:
            return device
    return None


def get_by_name(name: str) -> dict[str, Any] | None:
    lowered = (name or "").strip().lower()
    for device in _current():
        if device["name"] == lowered:
            return device
    return None


def can_view(principal, device: dict[str, Any]) -> bool:
    """Visibility comes from role_device_access, per role and per device.

    The deprecated `devices.access_roles` column is deliberately not consulted:
    it exists only so migration 0005 could backfill the new table.
    """
    if principal is None or principal.role_id is None:
        return False
    from ..access import bot_auth

    # Whoever manages devices sees all of them. Without this, an operator who
    # can edit or delete a device cannot see the one they just created, and
    # after migration nobody would see anything until access was granted one
    # device at a time — including from a UI that needs to list them first.
    if bot_auth.can(principal.role_id, "manage_devices"):
        return True
    return bot_auth.can_device(principal.role_id, device["id"], "view")


def can_control(principal, device: dict[str, Any], action: str | None = None) -> bool:
    """Whether this principal may switch the device.

    `action` selects "on" or "off". Omitting it asks "may control at all",
    which is true when either action is allowed.
    """
    if principal is None or principal.role_id is None:
        return False
    from ..access import bot_auth

    if bot_auth.can(principal.role_id, "manage_devices"):
        return True
    if action in ("on", "off"):
        return bot_auth.can_device(principal.role_id, device["id"], action)
    return bot_auth.can_device(principal.role_id, device["id"], "on") or bot_auth.can_device(
        principal.role_id, device["id"], "off"
    )
