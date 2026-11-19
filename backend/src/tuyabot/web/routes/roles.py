"""Roles API: list, create, update, delete with escalation guards."""

from __future__ import annotations

import re
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request

from ...access import permissions as perm_catalog
from ...access import roles as roles_module
from ...access import sessions
from ...storage.repos import api_keys as api_keys_repo
from ...storage.repos import audit, role_devices, roles
from ...storage.repos import devices as devices_repo
from ..deps import Principal, request_id, require

router = APIRouter(prefix="/api/roles", tags=["roles"])

SLUG_RE = re.compile(r"^[a-z][a-z0-9_-]{1,31}$")


def _validate_permissions(principal: Principal, requested: list[str]) -> list[str]:
    unknown = [key for key in requested if key not in perm_catalog.CATALOG]
    if unknown:
        raise HTTPException(
            status_code=422,
            detail={"errors": [{"key": "permissions", "message": f"izin tidak dikenal: {', '.join(unknown)}"}]},
        )
    if not perm_catalog.is_subset(requested, principal.permissions):
        raise HTTPException(
            status_code=403,
            detail="Tidak boleh memberi izin yang tidak Anda miliki",
        )
    return sorted(set(requested))


def _guard_protected(role: dict, requested: list[str]) -> None:
    if role["is_protected"]:
        missing = perm_catalog.PROTECTED_REQUIRED - set(requested)
        if missing:
            raise HTTPException(
                status_code=409,
                detail=f"Izin inti role terlindungi tidak boleh dicabut: {', '.join(sorted(missing))}",
            )


@router.get("")
async def list_roles(principal: Principal = Depends(require("users.view"))) -> dict[str, Any]:
    return {"roles": roles.list_all()}


@router.get("/permissions")
async def permission_catalog(principal: Principal = Depends(require("users.view"))) -> dict[str, Any]:
    return perm_catalog.catalog_payload()


@router.post("")
async def create_role(
    payload: dict[str, Any],
    request: Request,
    principal: Principal = Depends(require("roles.manage")),
) -> dict[str, Any]:
    slug = str(payload.get("slug", "")).strip()
    if not SLUG_RE.match(slug):
        raise HTTPException(
            status_code=422,
            detail={"errors": [{"key": "slug", "message": "slug: huruf kecil, angka, - atau _"}]},
        )
    requested = payload.get("permissions") or []
    if not isinstance(requested, list):
        raise HTTPException(status_code=422, detail={"errors": [{"key": "permissions", "message": "harus array"}]})
    clean = _validate_permissions(principal, [str(key) for key in requested])

    try:
        role_id = roles.create(slug, str(payload.get("name", slug)), payload.get("description"), clean)
    except Exception as exc:
        if "UNIQUE" in str(exc):
            raise HTTPException(status_code=409, detail="Slug role sudah dipakai") from exc
        raise

    audit.write(
        principal.actor_kind, principal.actor_id, principal.label, "roles.create",
        target_kind="role", target_id=role_id, details={"slug": slug, "permissions": clean},
        ip=request.client.host if request.client else None,
        request_id=request_id(request),
    )
    return roles.get(role_id) or {}


@router.patch("/{role_id}")
async def update_role(
    role_id: int,
    payload: dict[str, Any],
    request: Request,
    principal: Principal = Depends(require("roles.manage")),
) -> dict[str, Any]:
    role = roles.get(role_id)
    if role is None:
        raise HTTPException(status_code=404, detail="Role tidak ditemukan")

    before = {
        "permissions": role["permissions"],
        "name": role["name"],
        "rate_limit_per_minute": role["rate_limit_per_minute"],
    }

    requested = payload.get("permissions")
    clean = None
    if requested is not None:
        if not isinstance(requested, list):
            raise HTTPException(status_code=422, detail={"errors": [{"key": "permissions", "message": "harus array"}]})
        clean = _validate_permissions(principal, [str(key) for key in requested])
        _guard_protected(role, clean)
        if not perm_catalog.is_subset(roles_module.effective_permissions(role), principal.permissions):
            raise HTTPException(status_code=403, detail="Tidak boleh mengubah role dengan izin melebihi izin Anda")

    fields: dict[str, Any] = {}
    if clean is not None:
        fields["permissions"] = clean
    if "name" in payload:
        fields["name"] = str(payload["name"])
    if "description" in payload:
        fields["description"] = payload.get("description")
    if "rate_limit_per_minute" in payload:
        fields["rate_limit_per_minute"] = payload.get("rate_limit_per_minute")
    if role["is_protected"] and "name" in payload and str(payload["name"]) != role["name"]:
        pass  # name may change; slug and required permissions may not

    roles.update(role_id, **fields)

    revoked = 0
    if clean is not None and clean != before["permissions"]:
        # Users keep their role but must re-authenticate so stale permissions die.
        revoked = sessions.revoke_for_role(role_id)
        api_keys_repo.revoke_for_role(role_id)

    after = roles.get(role_id) or {}
    audit.write(
        principal.actor_kind, principal.actor_id, principal.label, "roles.update",
        target_kind="role", target_id=role_id,
        details={
            "before": before,
            "after": {
                "permissions": after.get("permissions"),
                "name": after.get("name"),
                "rate_limit_per_minute": after.get("rate_limit_per_minute"),
            },
            "sessions_revoked": revoked,
        },
        ip=request.client.host if request.client else None,
        request_id=request_id(request),
    )
    return after


@router.delete("/{role_id}")
async def delete_role(
    role_id: int,
    request: Request,
    principal: Principal = Depends(require("roles.manage")),
) -> dict[str, Any]:
    role = roles.get(role_id)
    if role is None:
        raise HTTPException(status_code=404, detail="Role tidak ditemukan")
    if role["is_protected"]:
        raise HTTPException(status_code=409, detail="Role terlindungi tidak bisa dihapus")
    if not perm_catalog.is_subset(roles_module.effective_permissions(role), principal.permissions):
        raise HTTPException(status_code=403, detail="Tidak boleh menghapus role dengan izin melebihi izin Anda")

    refs = roles.roles_referencing(role_id)
    if any(refs.values()):
        raise HTTPException(
            status_code=409,
            detail={"message": "Role masih dipakai", "references": refs},
        )

    roles.delete(role_id)
    audit.write(
        principal.actor_kind, principal.actor_id, principal.label, "roles.delete",
        target_kind="role", target_id=role_id, details={"slug": role["slug"]},
        ip=request.client.host if request.client else None,
        request_id=request_id(request),
    )
    return {"deleted": True}


@router.get("/{role_id}/devices")
async def list_role_devices(
    role_id: int,
    principal: Principal = Depends(require("roles.manage")),
) -> dict[str, Any]:
    if roles.get(role_id) is None:
        raise HTTPException(status_code=404, detail="Role tidak ditemukan")
    return {"entries": role_devices.get_for_role(role_id)}


@router.put("/{role_id}/devices")
async def set_role_devices(
    role_id: int,
    payload: dict[str, Any],
    request: Request,
    principal: Principal = Depends(require("roles.manage")),
) -> dict[str, Any]:
    """Replace the role's whole matrix.

    Replace, not merge: the editor sends every row it shows, so a device
    removed from the table must stop being reachable.
    """
    if roles.get(role_id) is None:
        raise HTTPException(status_code=404, detail="Role tidak ditemukan")

    entries = payload.get("entries")
    if not isinstance(entries, list):
        raise HTTPException(status_code=422, detail={"errors": [{"key": "entries", "message": "entries harus array"}]})

    known = {device["id"] for device in devices_repo.list_all()}
    normalized = []
    for entry in entries:
        device_id = entry.get("device_id")
        if device_id not in known:
            raise HTTPException(
                status_code=422,
                detail={"errors": [{"key": "device_id", "message": f"Perangkat {device_id} tidak ada"}]},
            )
        normalized.append({
            "device_id": device_id,
            "can_view": bool(entry.get("can_view")),
            "can_on": bool(entry.get("can_on")),
            "can_off": bool(entry.get("can_off")),
        })

    role_devices.set_for_role(role_id, normalized)
    audit.write(
        principal.actor_kind, principal.actor_id, principal.label, "roles.devices",
        target_kind="role", target_id=role_id, details={"devices": len(normalized)},
        ip=request.client.host if request.client else None,
        request_id=request_id(request),
    )
    return {"entries": role_devices.get_for_role(role_id)}
