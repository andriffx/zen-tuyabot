"""Request authentication/authorization dependencies.

Task 3 needs `Principal` and `require()` before sessions exist (Task 4). The
session resolution here is deliberately minimal and is replaced/extended by
`access/sessions.py` in Task 4 — only `current_principal` changes.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from fastapi import Depends, Header, HTTPException, Request

from ..access import roles as roles_module  # noqa: F401 - re-exported for routes


@dataclass(frozen=True)
class Principal:
    actor_kind: str  # web | telegram | api_key | system
    actor_id: int | None
    label: str | None
    role_id: int | None
    role_slug: str | None
    permissions: frozenset[str] = field(default_factory=frozenset)
    session_token: str | None = None

    @property
    def is_authenticated(self) -> bool:
        return self.role_id is not None

    def has(self, *keys: str) -> bool:
        return all(key in self.permissions for key in keys)


ANONYMOUS = Principal("system", None, None, None, None, frozenset())


def request_id(request: Request) -> str | None:
    return getattr(request.state, "request_id", None)


async def current_principal(request: Request, x_api_key: str = Header(default="")) -> Principal:
    """Resolve the caller. Task 4 adds cookie sessions; API keys work now."""
    from ..web import auth_state

    if x_api_key:
        principal = auth_state.resolve_api_key(x_api_key)
        if principal is None:
            raise HTTPException(status_code=401, detail="API key tidak valid")
        return principal

    session_token = request.cookies.get(auth_state.SESSION_COOKIE)
    if session_token:
        principal = auth_state.resolve_session(session_token, request)
        if principal is not None:
            return principal

    raise HTTPException(status_code=401, detail="Tidak terautentikasi")


def require(*permissions: str):
    """Dependency factory for web endpoints.

    The dashboard has exactly one account (the Superadmin created during setup),
    so there is no per-permission distinction left to enforce there: being
    authenticated *is* the authorization. Bot permissions (`monitoring`,
    `manage_users`, ...) belong to Telegram users and are checked by
    `access.bot_auth`, not here.

    The `permissions` argument is accepted and ignored so existing route
    declarations keep documenting intent, and so reintroducing web authorization
    later is a one-function change rather than an audit of every route.

    Denials used to be audited for escalation attempts; with a single account
    there is no escalation to audit, and the audit write itself required a
    permission row that no longer exists.
    """

    async def dependency(principal: Principal = Depends(current_principal)) -> Principal:
        return principal

    return dependency


def require_any(*permissions: str):
    """See `require`: authentication is the only web-side check."""

    async def dependency(principal: Principal = Depends(current_principal)) -> Principal:
        return principal

    return dependency
