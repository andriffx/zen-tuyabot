"""Telegram principal resolution and permission guards."""

from __future__ import annotations

import logging
from typing import Any

from ..access import permissions as perm_catalog
from ..access import roles as roles_module
from ..storage.repos import roles as roles_repo
from ..storage.repos import telegram_users
from ..web.deps import Principal

logger = logging.getLogger(__name__)


def resolve(telegram_id: int) -> Principal | None:
    """None means 'public': only /start and /help are available."""
    record = telegram_users.get(telegram_id)
    if record is None or not record.get("is_active"):
        return None

    role = roles_repo.get(record["role_id"])
    if role is None:
        return None

    telegram_users.touch(telegram_id)
    return Principal(
        actor_kind="telegram",
        actor_id=telegram_id,
        label=record.get("label") or str(telegram_id),
        role_id=role["id"],
        role_slug=role["slug"],
        permissions=roles_module.effective_permissions(role),
    )


def public_principal() -> Principal:
    return Principal("telegram", None, None, None, None, frozenset())


def can_grant(actor: Principal, role: dict[str, Any]) -> bool:
    """A Telegram user may hand out a role only if it is a subset of their own."""
    return perm_catalog.is_subset(roles_module.effective_permissions(role), actor.permissions)
