"""Read-only log endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query

from ...storage.repos import logs
from ..deps import Principal, require

router = APIRouter(prefix="/api/logs", tags=["logs"])


@router.get("/activities")
async def activities(
    limit: int = Query(default=50),
    offset: int = Query(default=0),
    device_id: int | None = Query(default=None),
    principal: Principal = Depends(require("view_logs")),
) -> dict[str, Any]:
    return {"items": logs.recent_activities(limit=limit, offset=offset, device_id=device_id)}


@router.get("/power")
async def power(
    limit: int = Query(default=50),
    offset: int = Query(default=0),
    device_id: int | None = Query(default=None),
    principal: Principal = Depends(require("view_logs")),
) -> dict[str, Any]:
    return {"items": logs.recent_power(limit=limit, offset=offset, device_id=device_id)}


@router.get("/errors")
async def errors(
    limit: int = Query(default=50),
    offset: int = Query(default=0),
    principal: Principal = Depends(require("view_logs")),
) -> dict[str, Any]:
    return {"items": logs.recent_errors(limit=limit, offset=offset)}
