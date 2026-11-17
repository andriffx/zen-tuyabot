"""Real auth implementation: sessions, API keys, and denial auditing."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from ..access import roles as roles_module
from ..access import sessions
from ..settings import service as settings_service
from ..storage.repos import api_keys, audit, roles
from .deps import Principal

if TYPE_CHECKING:
    from fastapi import Request

logger = logging.getLogger(__name__)


def _principal_from_role(
    role_id: int,
    *,
    actor_kind: str,
    actor_id: int | None,
    label: str | None,
    session_token: str | None = None,
) -> Principal | None:
    role = roles.get(role_id)
    if role is None:
        return None
    return Principal(
        actor_kind=actor_kind,
        actor_id=actor_id,
        label=label,
        role_id=role_id,
        role_slug=role["slug"],
        permissions=roles_module.effective_permissions(role),
        session_token=session_token,
    )


def resolve_api_key(raw_key: str) -> Principal | None:
    record = api_keys.resolve(raw_key)
    if record is None:
        return None
    return _principal_from_role(
        record["role_id"],
        actor_kind="api_key",
        actor_id=record["id"],
        label=f"api_key:{record['name']}",
    )


def resolve_session(token: str, request: Request) -> Principal | None:
    idle = settings_service.get_int("security.session_idle_minutes")
    session = sessions.resolve(token, idle_minutes=idle)
    if session is None:
        return None
    return _principal_from_role(
        session["role_id"],
        actor_kind="web",
        actor_id=session["user_id"],
        label=session["username"],
        session_token=token,
    )


def record_denial(principal: Principal, required: tuple[str, ...], request: Request) -> None:
    audit.write(
        principal.actor_kind,
        principal.actor_id,
        principal.label,
        "access.denied",
        target_kind="permission",
        target_id=",".join(required),
        result="denied",
        ip=request.client.host if request.client else None,
        details={"required": list(required), "path": request.url.path, "method": request.method},
        request_id=getattr(request.state, "request_id", None),
    )
