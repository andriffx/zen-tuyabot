"""Permission catalog — the single source of truth for authorization keys.

The catalog lives in code (not the DB) so role editors can build a stable
checkbox tree, and so a new permission never requires a data migration.
"""

from __future__ import annotations

from collections.abc import Collection, Iterable

CATEGORIES: dict[str, tuple[str, ...]] = {
    "Device": (
        "devices.view",
        "devices.control",
        "devices.manage",
        "devices.scan",
    ),
    "Log": (
        "logs.view",
        "logs.cleanup",
    ),
    "Settings": (
        "settings.view",
        "settings.edit",
    ),
    "Users web": (
        "users.view",
        "users.manage",
    ),
    "Users Telegram": (
        "telegram_users.view",
        "telegram_users.manage",
    ),
    "Roles": ("roles.manage",),
    "Bot": (
        "bots.view",
        "bots.manage",
    ),
    "Backup": (
        "backup.view",
        "backup.create",
        "backup.restore",
    ),
    "API key": ("apikeys.manage",),
    "Sistem": (
        "system.view",
        "audit.view",
        "system.maintenance",
        "system.restore",
    ),
}

CATALOG: tuple[str, ...] = tuple(key for keys in CATEGORIES.values() for key in keys)

# Permissions a protected role may never lose.
PROTECTED_REQUIRED: frozenset[str] = frozenset({"roles.manage", "users.manage", "system.view"})


def is_subset(sub: Iterable[str], sup: Collection[str]) -> bool:
    """True when every permission in `sub` is also in `sup`."""
    return set(sub) <= set(sup)


def catalog_payload() -> dict:
    """Shape used by the role editor UI."""
    return {
        "categories": [{"name": name, "permissions": list(keys)} for name, keys in CATEGORIES.items()],
        "all": list(CATALOG),
    }
