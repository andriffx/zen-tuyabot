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
    """Visibility rule.

    `access_roles` restricts ordinary viewers. A role holding `devices.manage`
    always sees every device: it can already edit or delete them, and a
    manager who cannot see a device they created cannot operate the system.
    """
    if principal is None or "devices.view" not in principal.permissions:
        return False
    if "devices.manage" in principal.permissions:
        return True
    allowed = device.get("access_roles") or []
    return not allowed or principal.role_id in allowed


def can_control(principal, device: dict[str, Any]) -> bool:
    if principal is None or "devices.control" not in principal.permissions:
        return False
    return can_view(principal, device)
