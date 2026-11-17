"""Hooks the auth layer fills in.

Task 3 defines the shape so routes and `deps` can be written and tested before
sessions exist. Task 4 replaces the resolvers with real implementations and
fills `record_denial` with a real audit write.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi import Request

    from .deps import Principal

SESSION_COOKIE = "tuyabot_session"
CSRF_COOKIE = "csrf_token"
CSRF_HEADER = "X-CSRF-Token"


def resolve_api_key(raw_key: str) -> Principal | None:
    """Placeholder until Task 4 installs the real lookup."""
    from . import auth_impl

    return auth_impl.resolve_api_key(raw_key)


def resolve_session(token: str, request: Request) -> Principal | None:
    from . import auth_impl

    return auth_impl.resolve_session(token, request)


def record_denial(principal: Principal, required: tuple[str, ...], request: Request) -> None:
    from . import auth_impl

    auth_impl.record_denial(principal, required, request)
