"""Telegram user management API (separate entity from web accounts)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request

from ...access import permissions as perm_catalog
from ...access import roles as roles_module
from ...storage.repos import audit, roles, telegram_users
from ..deps import Principal, request_id, require

router = APIRouter(prefix="/api/telegram-users", tags=["telegram-users"])


def _role_checked(principal: Principal, role_id: Any) -> dict:
    if not isinstance(role_id, int):
        raise HTTPException(status_code=422, detail={"errors": [{"key": "role_id", "message": "role_id wajib"}]})
    role = roles.get(role_id)
    if role is None:
        raise HTTPException(status_code=422, detail={"errors": [{"key": "role_id", "message": "Role tidak ada"}]})
    if not perm_catalog.is_subset(roles_module.effective_permissions(role), principal.permissions):
        raise HTTPException(status_code=403, detail="Tidak boleh memberi role dengan izin melebihi izin Anda")
    return role


def _target_guard(principal: Principal, record: dict) -> None:
    role = roles.get(record["role_id"])
    if role and not perm_catalog.is_subset(roles_module.effective_permissions(role), principal.permissions):
        raise HTTPException(status_code=403, detail="Tidak boleh mengubah user dengan izin melebihi izin Anda")


@router.get("")
async def list_users(principal: Principal = Depends(require("manage_users"))) -> dict[str, Any]:
    rows = telegram_users.list_all()
    for row in rows:
        row.pop("role_permissions", None)
    return {"telegram_users": rows}


@router.post("")
async def create_user(
    payload: dict[str, Any],
    request: Request,
    principal: Principal = Depends(require("manage_users")),
) -> dict[str, Any]:
    telegram_id = payload.get("telegram_id")
    if isinstance(telegram_id, bool) or not isinstance(telegram_id, int):
        raise HTTPException(
            status_code=422, detail={"errors": [{"key": "telegram_id", "message": "harus angka"}]}
        )
    role = _role_checked(principal, payload.get("role_id"))

    try:
        telegram_users.upsert(
            telegram_id,
            role["id"],
            label=payload.get("label"),
            created_by_web_user_id=principal.actor_id if principal.actor_kind == "web" else None,
        )
    except telegram_users.TelegramUserError as exc:
        raise HTTPException(status_code=422, detail={"errors": [{"key": exc.code, "message": exc.message}]}) from exc

    audit.write(
        principal.actor_kind, principal.actor_id, principal.label, "telegram_users.create",
        target_kind="telegram_user", target_id=telegram_id,
        details={"role_id": role["id"], "role_slug": role["slug"]},
        ip=request.client.host if request.client else None,
        request_id=request_id(request),
    )
    return telegram_users.get(telegram_id) or {}


@router.patch("/{telegram_id}")
async def update_user(
    telegram_id: int,
    payload: dict[str, Any],
    request: Request,
    principal: Principal = Depends(require("manage_users")),
) -> dict[str, Any]:
    record = telegram_users.get(telegram_id)
    if record is None:
        raise HTTPException(status_code=404, detail="User Telegram tidak ditemukan")
    _target_guard(principal, record)

    if "role_id" in payload:
        role = _role_checked(principal, payload["role_id"])
        telegram_users.upsert(
            telegram_id,
            role["id"],
            label=payload.get("label") or record.get("label"),
            created_by_web_user_id=record.get("created_by_web_user_id"),
        )
    elif "label" in payload:
        telegram_users.upsert(
            telegram_id,
            record["role_id"],
            label=payload["label"],
            created_by_web_user_id=record.get("created_by_web_user_id"),
        )

    if isinstance(payload.get("is_active"), bool):
        telegram_users.set_active(telegram_id, payload["is_active"])

    audit.write(
        principal.actor_kind, principal.actor_id, principal.label, "telegram_users.update",
        target_kind="telegram_user", target_id=telegram_id,
        details={
            "role_id": payload.get("role_id"),
            "label_changed": "label" in payload,
            "is_active": payload.get("is_active"),
        },
        ip=request.client.host if request.client else None,
        request_id=request_id(request),
    )
    return telegram_users.get(telegram_id) or {}


@router.delete("/{telegram_id}")
async def delete_user(
    telegram_id: int,
    request: Request,
    principal: Principal = Depends(require("manage_users")),
) -> dict[str, Any]:
    record = telegram_users.get(telegram_id)
    if record is None:
        raise HTTPException(status_code=404, detail="User Telegram tidak ditemukan")
    _target_guard(principal, record)

    telegram_users.delete(telegram_id)
    audit.write(
        principal.actor_kind, principal.actor_id, principal.label, "telegram_users.delete",
        target_kind="telegram_user", target_id=telegram_id,
        ip=request.client.host if request.client else None,
        request_id=request_id(request),
    )
    return {"deleted": True}
