"""Server-sent events: device snapshots read from the cache, never from devices.

Ten open dashboards produce ten SSE streams and zero extra device traffic.
"""

from __future__ import annotations

import asyncio
import json
import time
from typing import Any

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from ...devices import registry
from ...infra import state_cache
from ...settings import service as settings_service
from ..deps import Principal, require

router = APIRouter(prefix="/api", tags=["stream"])


def _device_payload(device: dict[str, Any]) -> dict[str, Any]:
    status = state_cache.cache.read((device["name"], "status")) or {}
    age = state_cache.cache.age((device["name"], "status"))
    return {
        "id": device["id"],
        "name": device["name"],
        "label": device["label"],
        "online": bool(status.get("success")),
        "switch_on": status.get("switch_on"),
        "power_w": status.get("power_w"),
        "voltage_v": status.get("voltage_v"),
        "current_a": status.get("current_a"),
        "age_seconds": round(age, 1) if age is not None else None,
    }


def build_snapshot(principal: Principal) -> dict[str, Any]:
    devices = registry.visible_to(principal)
    return {
        "ts": time.time(),
        "devices": [_device_payload(device) for device in devices],
    }


@router.get("/stream")
async def stream(
    principal: Principal = Depends(require("monitoring")),
) -> StreamingResponse:
    interval = max(1.0, float(settings_service.get_float("monitoring.warm_interval_seconds") / 20))

    async def events():
        last = None
        while True:
            payload = json.dumps(build_snapshot(principal), separators=(",", ":"), default=str)
            if payload != last:
                last = payload
                yield f"data: {payload}\n\n"
            else:
                yield ": keepalive\n\n"
            await asyncio.sleep(interval)

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"},
    )
