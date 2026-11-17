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
    """Dependency factory: 403 unless the caller holds every permission.

    Every denial is audited with result=denied so privilege escalation attempts
    are visible in the audit log.
    """

    async def dependency(request: Request, principal: Principal = Depends(current_principal)) -> Principal:
        from ..web import auth_state

        if not principal.has(*permissions):
            auth_state.record_denial(principal, permissions, request)
            raise HTTPException(status_code=403, detail="Tidak berizin")
        return principal

    return dependency


def require_any(*permissions: str):
    async def dependency(request: Request, principal: Principal = Depends(current_principal)) -> Principal:
        from ..web import auth_state

        if not any(key in principal.permissions for key in permissions):
            auth_state.record_denial(principal, permissions, request)
            raise HTTPException(status_code=403, detail="Tidak berizin")
        return principal

    return dependency
