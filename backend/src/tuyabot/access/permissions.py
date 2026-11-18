"""Permission catalog — the single source of truth for authorization keys.

The catalog lives in code (not the DB) so role editors can build a stable
checkbox tree, and so a new permission never requires a data migration.
"""

from __future__ import annotations

from collections.abc import Collection, Iterable

CATEGORIES: dict[str, tuple[str, ...]] = {
    "Bot": (
        "monitoring",
        "manage_users",
        "manage_devices",
        "view_logs",
    ),
}

CATALOG: tuple[str, ...] = tuple(key for keys in CATEGORIES.values() for key in keys)

# Permissions a protected role may never lose.
PROTECTED_REQUIRED: frozenset[str] = frozenset({"manage_users"})


def is_subset(sub: Iterable[str], sup: Collection[str]) -> bool:
    """True when every permission in `sub` is also in `sup`."""
    return set(sub) <= set(sup)


def catalog_payload() -> dict:
    """Shape used by the role editor UI."""
    return {
        "categories": [{"name": name, "permissions": list(keys)} for name, keys in CATEGORIES.items()],
        "all": list(CATALOG),
    }
