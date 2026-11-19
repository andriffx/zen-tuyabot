"""Stats and readiness endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from ...storage.repos import stats as stats_repo
from ..deps import Principal, current_principal, require

router = APIRouter(prefix="/api", tags=["stats"])


@router.get("/stats")
async def read_stats(principal: Principal = Depends(require("monitoring"))) -> dict[str, Any]:
    return stats_repo.stats()


@router.get("/health")
async def read_health(principal: Principal = Depends(current_principal)) -> dict[str, Any]:
    return stats_repo.health()
