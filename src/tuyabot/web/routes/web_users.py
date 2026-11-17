"""Web user management: creation is Superadmin-only and never self-service."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request

from ...access import permissions as perm_catalog
from ...access import roles as roles_module
from ...access import sessions
from ...storage.repos import audit, roles, web_users
from ..deps import Principal, request_id, require

router = APIRouter(prefix="/api/web-users", tags=["web-users"])


def _check_role_subset(principal: Principal, role_id: int) -> dict:
    role = roles.get(role_id)
    if role is None:
        raise HTTPException(status_code=422, detail={"errors": [{"key": "role_id", "message": "Role tidak ada"}]})
    target_perms = roles_module.effective_permissions(role)
    if not perm_catalog.is_subset(target_perms, principal.permissions):
        raise HTTPException(
            status_code=403,
            detail="Tidak boleh memberikan role dengan izin melebihi izin Anda",
        )
    return role


def _check_target_editable(principal: Principal, target: dict) -> None:
    target_role = roles.get(target["role_id"])
    if target_role and not perm_catalog.is_subset(
        roles_module.effective_permissions(target_role), principal.permissions
    ):
        raise HTTPException(status_code=403, detail="Tidak boleh mengubah akun dengan izin melebihi izin Anda")


def _last_manager_guard(target: dict, *, deactivating: bool) -> None:
    if not deactivating or not target["is_active"]:
        return
    role = roles.get(target["role_id"])
    if role and "users.manage" in role["permissions"] and web_users.count_active_managers() <= 1:
        raise HTTPException(
            status_code=409,
            detail="Tidak bisa menonaktifkan admin aktif terakhir yang memegang users.manage",
        )


@router.get("")
async def list_users(principal: Principal = Depends(require("users.view"))) -> dict[str, Any]:
    users = web_users.list_all()
    role_names = {role["id"]: role for role in roles.list_all()}
    for user in users:
        role = role_names.get(user["role_id"], {})
        user["role"] = {"id": role.get("id"), "slug": role.get("slug"), "name": role.get("name")}
    return {"users": users}


@router.post("")
async def create_user(
    payload: dict[str, Any],
    request: Request,
    principal: Principal = Depends(require("users.manage")),
) -> dict[str, Any]:
    role_id = payload.get("role_id")
    if not isinstance(role_id, int):
        raise HTTPException(status_code=422, detail={"errors": [{"key": "role_id", "message": "role_id wajib"}]})
    _check_role_subset(principal, role_id)

    try:
        user_id = web_users.create(
            str(payload.get("username", "")),
            str(payload.get("password", "")),
            role_id,
            created_by=principal.actor_id if principal.actor_kind == "web" else None,
        )
    except web_users.UserError as exc:
        raise HTTPException(status_code=422, detail={"errors": [{"key": exc.code, "message": exc.message}]}) from exc

    audit.write(
        principal.actor_kind, principal.actor_id, principal.label, "web_users.create",
        target_kind="web_user", target_id=user_id,
        details={"username": payload.get("username"), "role_id": role_id},
        ip=request.client.host if request.client else None,
        request_id=request_id(request),
    )
    return web_users.get(user_id) or {}


@router.patch("/{user_id}")
async def update_user(
    user_id: int,
    payload: dict[str, Any],
    request: Request,
    principal: Principal = Depends(require("users.manage")),
) -> dict[str, Any]:
    target = web_users.get(user_id)
    if target is None:
        raise HTTPException(status_code=404, detail="User tidak ditemukan")
    _check_target_editable(principal, target)

    new_role_id = payload.get("role_id")
    if new_role_id is not None:
        if not isinstance(new_role_id, int):
            raise HTTPException(status_code=422, detail={"errors": [{"key": "role_id", "message": "harus angka"}]})
        _check_role_subset(principal, new_role_id)

    is_active = payload.get("is_active")
    if isinstance(is_active, bool):
        _last_manager_guard(target, deactivating=not is_active)

    password = payload.get("password")
    try:
        web_users.update(
            user_id,
            password=str(password) if password is not None else None,
            role_id=new_role_id,
            is_active=is_active if isinstance(is_active, bool) else None,
        )
    except web_users.UserError as exc:
        raise HTTPException(status_code=422, detail={"errors": [{"key": exc.code, "message": exc.message}]}) from exc

    revoked = 0
    if password is not None or new_role_id is not None or is_active is False:
        revoked = sessions.revoke_for_user(user_id)

    audit.write(
        principal.actor_kind, principal.actor_id, principal.label, "web_users.update",
        target_kind="web_user", target_id=user_id,
        details={
            "role_id": new_role_id,
            "is_active": is_active,
            "password_changed": password is not None,
            "sessions_revoked": revoked,
        },
        ip=request.client.host if request.client else None,
        request_id=request_id(request),
    )
    return web_users.get(user_id) or {}


@router.delete("/{user_id}")
async def delete_user(
    user_id: int,
    request: Request,
    principal: Principal = Depends(require("users.manage")),
) -> dict[str, Any]:
    target = web_users.get(user_id)
    if target is None:
        raise HTTPException(status_code=404, detail="User tidak ditemukan")
    _check_target_editable(principal, target)
    _last_manager_guard(target, deactivating=True)

    sessions.revoke_for_user(user_id)
    web_users.delete(user_id)

    audit.write(
        principal.actor_kind, principal.actor_id, principal.label, "web_users.delete",
        target_kind="web_user", target_id=user_id,
        details={"username": target["username"]},
        ip=request.client.host if request.client else None,
        request_id=request_id(request),
    )
    return {"deleted": True}
