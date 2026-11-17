"""Effective permissions for a role, and ancillary role helpers."""

from __future__ import annotations

from typing import Any

from . import permissions


def effective_permissions(role: dict[str, Any] | None) -> frozenset[str]:
    """Stored permissions intersected with the catalog.

    Anything a retired permission key leaves behind in an old row is ignored,
    so removing a permission from the catalog never grants anything new.
    """
    if not role:
        return frozenset()
    stored = role.get("permissions") or []
    return frozenset(key for key in stored if key in permissions.CATALOG)


def has(perms: frozenset[str], *required: str) -> bool:
    return all(key in perms for key in required)
