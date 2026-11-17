"""Bot management API: tokens are write-only, one token per row."""

from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request

from ...storage.repos import audit
from ...storage.repos import bots as bots_repo
from ...telegram import manager as manager_module
from ..deps import Principal, request_id, require

router = APIRouter(prefix="/api/bots", tags=["bots"])


def _web_actor(principal: Principal) -> int | None:
    """created_by is a web_users foreign key; API keys and bots have no row there."""
    return principal.actor_id if principal.actor_kind == "web" else None


def _schedule(coro) -> None:
    """Start bot lifecycle work on the main loop without blocking the request."""
    try:
        asyncio.get_running_loop().create_task(coro)
    except RuntimeError:
        coro.close()


@router.get("")
async def list_bots(principal: Principal = Depends(require("bots.view"))) -> dict[str, Any]:
    bots = bots_repo.list_all()
    statuses = manager_module.manager.status()
    for bot in bots:
        bot["runtime_status"] = statuses.get(bot["id"], "stopped" if not bot["enabled"] else "unknown")
    return {"bots": bots}


@router.post("")
async def create_bot(
    payload: dict[str, Any],
    request: Request,
    principal: Principal = Depends(require("bots.manage")),
) -> dict[str, Any]:
    label = str(payload.get("label", "")).strip() or "Bot"
    token = str(payload.get("token", "")).strip()
    try:
        bot_id = bots_repo.create(
            label, token, created_by=_web_actor(principal)
        )
    except bots_repo.BotError as exc:
        raise HTTPException(status_code=409, detail={"errors": [{"key": exc.code, "message": exc.message}]}) from exc

    audit.write(
        principal.actor_kind, principal.actor_id, principal.label, "bots.create",
        target_kind="bot", target_id=bot_id,
        details={"label": label, "token_changed": True},
        ip=request.client.host if request.client else None,
        request_id=request_id(request),
    )
    record = bots_repo.get(bot_id) or {}
    record.pop("token", None)
    record.pop("token_sha256", None)
    return record


@router.patch("/{bot_id}")
async def update_bot(
    bot_id: int,
    payload: dict[str, Any],
    request: Request,
    principal: Principal = Depends(require("bots.manage")),
) -> dict[str, Any]:
    record = bots_repo.get(bot_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Bot tidak ditemukan")

    token = payload.get("token")
    enabled = payload.get("enabled")
    try:
        bots_repo.update(
            bot_id,
            label=payload.get("label"),
            token=str(token) if token else None,
            enabled=enabled if isinstance(enabled, bool) else None,
        )
    except bots_repo.BotError as exc:
        raise HTTPException(status_code=409, detail={"errors": [{"key": exc.code, "message": exc.message}]}) from exc

    if token:
        _schedule(manager_module.manager.rebuild(bot_id))
    elif isinstance(enabled, bool):
        _schedule(
            manager_module.manager.enable(bot_id)
            if enabled
            else manager_module.manager.disable(bot_id)
        )

    audit.write(
        principal.actor_kind, principal.actor_id, principal.label, "bots.update",
        target_kind="bot", target_id=bot_id,
        details={"label_changed": "label" in payload, "token_changed": bool(token), "enabled": enabled},
        ip=request.client.host if request.client else None,
        request_id=request_id(request),
    )
    fresh = bots_repo.get(bot_id) or {}
    fresh.pop("token", None)
    fresh.pop("token_sha256", None)
    return fresh


@router.post("/{bot_id}/enable")
async def enable_bot(
    bot_id: int,
    request: Request,
    principal: Principal = Depends(require("bots.manage")),
) -> dict[str, Any]:
    if bots_repo.get(bot_id) is None:
        raise HTTPException(status_code=404, detail="Bot tidak ditemukan")
    bots_repo.update(bot_id, enabled=True)
    status = await manager_module.manager.enable(bot_id)
    audit.write(
        principal.actor_kind, principal.actor_id, principal.label, "bots.enable",
        target_kind="bot", target_id=bot_id, details={"status": status},
        ip=request.client.host if request.client else None,
        request_id=request_id(request),
    )
    return {"status": status}


@router.post("/{bot_id}/disable")
async def disable_bot(
    bot_id: int,
    request: Request,
    principal: Principal = Depends(require("bots.manage")),
) -> dict[str, Any]:
    if bots_repo.get(bot_id) is None:
        raise HTTPException(status_code=404, detail="Bot tidak ditemukan")
    bots_repo.update(bot_id, enabled=False)
    status = await manager_module.manager.disable(bot_id)
    audit.write(
        principal.actor_kind, principal.actor_id, principal.label, "bots.disable",
        target_kind="bot", target_id=bot_id,
        ip=request.client.host if request.client else None,
        request_id=request_id(request),
    )
    return {"status": status}


@router.post("/{bot_id}/test")
async def test_bot(
    bot_id: int,
    principal: Principal = Depends(require("bots.manage")),
) -> dict[str, Any]:
    token = bots_repo.get_token(bot_id)
    if token is None:
        raise HTTPException(status_code=404, detail="Bot tidak ditemukan")
    result = await asyncio.to_thread(manager_module.validate_token_sync, token)
    if result.get("ok"):
        bots_repo.record_ok(bot_id, result.get("username"))
    return result


@router.delete("/{bot_id}")
async def delete_bot(
    bot_id: int,
    request: Request,
    principal: Principal = Depends(require("bots.manage")),
) -> dict[str, Any]:
    if bots_repo.get(bot_id) is None:
        raise HTTPException(status_code=404, detail="Bot tidak ditemukan")
    _schedule(manager_module.manager.disable(bot_id))
    bots_repo.delete(bot_id)
    audit.write(
        principal.actor_kind, principal.actor_id, principal.label, "bots.delete",
        target_kind="bot", target_id=bot_id,
        ip=request.client.host if request.client else None,
        request_id=request_id(request),
    )
    return {"deleted": True}
