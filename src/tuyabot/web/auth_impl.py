"""Default (unauthenticated) auth implementation; Task 4 replaces it."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi import Request

    from .deps import Principal


def resolve_api_key(raw_key: str) -> Principal | None:
    return None


def resolve_session(token: str, request: Request) -> Principal | None:
    return None


def record_denial(principal: Principal, required: tuple[str, ...], request: Request) -> None:
    return None
