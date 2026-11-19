"""API key management for scripts and automation."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request

from ...access import permissions as perm_catalog
from ...access import roles as roles_module
from ...storage.repos import api_keys, audit, roles
from ..deps import Principal, request_id, require

router = APIRouter(prefix="/api/api-keys", tags=["api-keys"])


@router.get("")
async def list_keys(principal: Principal = Depends(require("manage_users"))) -> dict[str, Any]:
    role_names = {role["id"]: role for role in roles.list_all()}
    keys = []
    for key in api_keys.list_all():
        role = role_names.get(key["role_id"], {})
        key["role"] = {"id": role.get("id"), "slug": role.get("slug"), "name": role.get("name")}
        keys.append(key)
    return {"api_keys": keys}


@router.post("")
async def create_key(
    payload: dict[str, Any],
    request: Request,
    principal: Principal = Depends(require("manage_users")),
) -> dict[str, Any]:
    role_id = payload.get("role_id")
    if not isinstance(role_id, int):
        raise HTTPException(status_code=422, detail={"errors": [{"key": "role_id", "message": "role_id wajib"}]})
    role = roles.get(role_id)
    if role is None:
        raise HTTPException(status_code=422, detail={"errors": [{"key": "role_id", "message": "Role tidak ada"}]})
    if not perm_catalog.is_subset(roles_module.effective_permissions(role), principal.permissions):
        raise HTTPException(status_code=403, detail="Tidak boleh membuat API key dengan izin melebihi izin Anda")

    name = str(payload.get("name", "")).strip() or f"key-{role['slug']}"
    key_id, raw = api_keys.create(
        name, role_id, created_by=principal.actor_id if principal.actor_kind == "web" else None
    )

    audit.write(
        principal.actor_kind, principal.actor_id, principal.label, "api_keys.create",
        target_kind="api_key", target_id=key_id, details={"name": name, "role_id": role_id},
        ip=request.client.host if request.client else None,
        request_id=request_id(request),
    )
    # Shown exactly once; never retrievable afterwards.
    return {"id": key_id, "name": name, "key": raw}


@router.delete("/{key_id}")
async def delete_key(
    key_id: int,
    request: Request,
    principal: Principal = Depends(require("manage_users")),
) -> dict[str, Any]:
    api_keys.delete(key_id)
    audit.write(
        principal.actor_kind, principal.actor_id, principal.label, "api_keys.delete",
        target_kind="api_key", target_id=key_id,
        ip=request.client.host if request.client else None,
        request_id=request_id(request),
    )
    return {"deleted": True}
