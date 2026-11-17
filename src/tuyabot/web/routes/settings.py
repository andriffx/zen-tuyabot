"""Settings API: read effective values, patch atomically."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request

from ...settings import registry, service
from ...storage.repos import audit
from ..deps import Principal, request_id, require

router = APIRouter(prefix="/api/settings", tags=["settings"])


def _actor_details(principal: Principal) -> dict[str, Any]:
    return {
        "actor_kind": principal.actor_kind,
        "actor_id": principal.actor_id,
        "actor_label": principal.label,
    }


@router.get("")
async def read_settings(principal: Principal = Depends(require("settings.view"))) -> dict[str, Any]:
    return {"values": service.all_values(), "schema": service.schema()}


@router.get("/schema")
async def read_schema(principal: Principal = Depends(require("settings.view"))) -> dict[str, Any]:
    return {"schema": service.schema()}


@router.patch("")
async def patch_settings(
    payload: dict[str, Any],
    request: Request,
    principal: Principal = Depends(require("settings.edit")),
) -> dict[str, Any]:
    values = payload.get("values")
    if not isinstance(values, dict):
        raise HTTPException(status_code=422, detail="body harus berisi objek 'values'")

    try:
        changed = service.patch(values, actor={"id": principal.actor_id})
    except registry.ValidationError as exc:
        raise HTTPException(
            status_code=422,
            detail={"errors": [{"key": exc.key, "message": exc.message}]},
        ) from exc

    audit.write(
        principal.actor_kind,
        principal.actor_id,
        principal.label,
        "settings.patch",
        target_kind="settings",
        details={"changed": {key: {"old": value["old"], "new": value["new"]} for key, value in changed.items()}},
        ip=request.client.host if request.client else None,
        request_id=request_id(request),
    )
    return {"changed": changed, "values": service.all_values(), "schema": service.schema()}
