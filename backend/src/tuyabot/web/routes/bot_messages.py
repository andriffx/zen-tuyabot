"""Bot message templates: list, edit, preview, and send a test.

The dashboard drives these; nothing here is reachable from the Telegram side.
Editing is restricted to whoever may manage Telegram users, since the texts
decide what those users see.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request

from ...storage.repos import audit, bot_messages
from ..deps import Principal, request_id, require

router = APIRouter(prefix="/api/bot-messages", tags=["bot-messages"])

# Sample values so a preview shows something concrete for every placeholder.
_SAMPLES: dict[str, str] = {
    "name": "Budi",
    "role": "Operator",
    "uid": "123456789",
    "id": "123456789",
    "label": "Budi",
    "active": "",
    "action": "menyalakan perangkat",
    "device": "Pompa Air",
    "message": "perangkat tidak membalas",
    "minutes": "30",
    "power": "12.5",
    "user_name": "Budi",
    "username": "budi",
    "user_id": "123456789",
    "reason": "melewati batas waktu",
    "timestamp": "2026-11-19 20:00:00",
}


@router.get("")
async def list_messages(principal: Principal = Depends(require("manage_users"))) -> dict[str, Any]:
    return {"messages": bot_messages.all_messages()}


@router.put("/{key}")
async def update_message(
    key: str,
    payload: dict[str, Any],
    request: Request,
    principal: Principal = Depends(require("manage_users")),
) -> dict[str, Any]:
    if key not in bot_messages.SEED:
        raise HTTPException(status_code=404, detail="Kunci pesan tidak dikenal")
    text = str(payload.get("text", ""))
    try:
        bot_messages.set_text(key, text)
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail={"errors": [{"key": "text", "message": str(exc)}]},
        ) from exc

    audit.write(
        principal.actor_kind, principal.actor_id, principal.label, "bot_messages.update",
        target_kind="bot_message", target_id=key,
        ip=request.client.host if request.client else None,
        request_id=request_id(request),
    )
    return {"key": key, "text": text}


@router.post("/{key}/preview")
async def preview_message(
    key: str,
    payload: dict[str, Any] | None = None,
    principal: Principal = Depends(require("manage_users")),
) -> dict[str, Any]:
    """Render with sample values, or with the caller's own values."""
    if key not in bot_messages.SEED:
        raise HTTPException(status_code=404, detail="Kunci pesan tidak dikenal")
    values = dict(_SAMPLES)
    if payload:
        values.update({k: str(v) for k, v in payload.items()})
    return {"key": key, "text": bot_messages.render(key, **values)}
