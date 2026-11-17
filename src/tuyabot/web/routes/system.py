"""Maintenance mode API and audit log API."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query, Request

from ...maintenance import service as maintenance_service
from ...storage.repos import audit
from ..deps import Principal, request_id, require

router = APIRouter(prefix="/api", tags=["system"])


@router.get("/maintenance/status")
async def maintenance_status() -> dict[str, Any]:
    """Public within an authenticated session: the SPA needs it to render the banner."""
    return {"maintenance": maintenance_service.is_on()}


@router.get("/maintenance")
async def read_maintenance(principal: Principal = Depends(require("system.view"))) -> dict[str, Any]:
    return {"maintenance": maintenance_service.is_on(), "state": maintenance_service.current()}


@router.post("/maintenance")
async def toggle_maintenance(
    payload: dict[str, Any],
    request: Request,
    principal: Principal = Depends(require("system.maintenance")),
) -> dict[str, Any]:
    enabled = bool(payload.get("enabled", True))
    reason = payload.get("reason")
    if enabled:
        minutes = payload.get("auto_off_minutes")
        try:
            from ...settings import service as settings_service

            minutes = int(minutes) if minutes else settings_service.get_int("maintenance.auto_off_minutes")
        except (TypeError, ValueError):
            minutes = None
        state = maintenance_service.enable(reason=reason, auto_off_minutes=minutes)
    else:
        state = maintenance_service.disable()

    audit.write(
        principal.actor_kind, principal.actor_id, principal.label,
        "maintenance.enable" if enabled else "maintenance.disable",
        target_kind="system", target_id="maintenance",
        details={"reason": reason, "state": state},
        ip=request.client.host if request.client else None,
        request_id=request_id(request),
    )
    return {"maintenance": maintenance_service.is_on(), "state": state}


@router.get("/audit")
async def read_audit(
    limit: int = Query(default=50),
    offset: int = Query(default=0),
    actor_kind: str | None = Query(default=None),
    action: str | None = Query(default=None),
    result: str | None = Query(default=None),
    target_kind: str | None = Query(default=None),
    request_id_filter: str | None = Query(default=None, alias="request_id"),
    since: str | None = Query(default=None),
    until: str | None = Query(default=None),
    principal: Principal = Depends(require("audit.view")),
) -> dict[str, Any]:
    rows = audit.list_page(
        limit=limit,
        offset=offset,
        actor_kind=actor_kind,
        action=action,
        result=result,
        target_kind=target_kind,
        request_id=request_id_filter,
        since=since,
        until=until,
    )
    return {"items": rows, "limit": limit, "offset": offset}
