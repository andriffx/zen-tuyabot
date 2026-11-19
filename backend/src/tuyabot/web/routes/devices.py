"""Device API: CRUD, control, status, scan, test."""

from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request

from ...devices import controller, diagnostics, registry, service
from ...devices import dps as dps_module
from ...infra import state_cache
from ...storage.repos import audit, logs
from ...storage.repos import devices as devices_repo
from ..deps import Principal, request_id, require

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/devices", tags=["devices"])

_scan_jobs: dict[str, dict[str, Any]] = {}
_scan_lock = asyncio.Lock()

# Control verification, following the reference implementation: give the relay
# time to move, read the DP back, and retry a few times. Tuya devices accept a
# frame for a DP that does not exist and answer with a null ACK, so the ACK
# alone cannot be reported as success.
CONTROL_ATTEMPTS = 3
CONTROL_VERIFY_DELAY = 0.4


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def _public_device(device: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": device["id"],
        "name": device["name"],
        "label": device["label"],
        "type": device["type"],
        "ip": device["ip"],
        "version": device["version"],
        "dps": device["dps"],
        "features": device["features"],
        "access_roles": device["access_roles"],
        "is_active": device["is_active"],
        "sort_order": device["sort_order"],
        "last_seen_at": device.get("last_seen_at"),
        "last_error": device.get("last_error"),
        # local_key and tuya_id are secrets from the UI's point of view:
        # tuya_id is not needed for display, local_key must never be returned.
        "has_local_key": bool(device.get("local_key")),
    }


def _resolve_visible(principal: Principal, device_id: int) -> dict[str, Any]:
    device = registry.get(device_id)
    if device is None or not registry.can_view(principal, device):
        # 404 for invisible devices so their existence does not leak.
        raise HTTPException(status_code=404, detail="Perangkat tidak ditemukan")
    return device


@router.get("")
async def list_devices(principal: Principal = Depends(require("devices.view"))) -> dict[str, Any]:
    devices = registry.visible_to(principal)
    return {"devices": [_public_device(device) for device in devices]}


@router.get("/templates")
async def list_templates(principal: Principal = Depends(require("devices.view"))) -> dict[str, Any]:
    return {
        "templates": dps_module.TEMPLATES,
        "types": list(dps_module.DEVICE_TYPES),
        "features": list(dps_module.FEATURES),
    }


@router.post("")
async def create_device(
    payload: dict[str, Any],
    request: Request,
    principal: Principal = Depends(require("devices.manage")),
) -> dict[str, Any]:
    try:
        device_id = devices_repo.create(payload)
    except devices_repo.DeviceError as exc:
        raise HTTPException(status_code=422, detail={"errors": [{"key": exc.code, "message": exc.message}]}) from exc

    registry.reload()
    audit.write(
        principal.actor_kind, principal.actor_id, principal.label, "devices.create",
        target_kind="device", target_id=device_id,
        details={"name": payload.get("name"), "type": payload.get("type")},
        ip=_client_ip(request), request_id=request_id(request),
    )
    return _public_device(registry.get(device_id) or {})


@router.patch("/{device_id}")
async def update_device(
    device_id: int,
    payload: dict[str, Any],
    request: Request,
    principal: Principal = Depends(require("devices.manage")),
) -> dict[str, Any]:
    before = devices_repo.get(device_id)
    if before is None:
        raise HTTPException(status_code=404, detail="Perangkat tidak ditemukan")

    try:
        devices_repo.update(device_id, payload)
    except devices_repo.DeviceError as exc:
        raise HTTPException(status_code=422, detail={"errors": [{"key": exc.code, "message": exc.message}]}) from exc

    controller.controller.forget(device_id)
    state_cache.cache.invalidate(before["name"])
    registry.reload()

    changed = {
        key: value
        for key, value in payload.items()
        if key != "local_key"  # never write the key into the audit log
    }
    audit.write(
        principal.actor_kind, principal.actor_id, principal.label, "devices.update",
        target_kind="device", target_id=device_id,
        details={"changed": changed, "local_key_changed": "local_key" in payload},
        ip=_client_ip(request), request_id=request_id(request),
    )
    return _public_device(registry.get(device_id) or {})


@router.delete("/{device_id}")
async def delete_device(
    device_id: int,
    request: Request,
    principal: Principal = Depends(require("devices.manage")),
) -> dict[str, Any]:
    device = devices_repo.get(device_id)
    if device is None:
        raise HTTPException(status_code=404, detail="Perangkat tidak ditemukan")

    controller.controller.forget(device_id)
    state_cache.cache.invalidate(device["name"])
    devices_repo.delete(device_id)
    registry.reload()

    audit.write(
        principal.actor_kind, principal.actor_id, principal.label, "devices.delete",
        target_kind="device", target_id=device_id, details={"name": device["name"]},
        ip=_client_ip(request), request_id=request_id(request),
    )
    return {"deleted": True}


@router.post("/{device_id}/on")
async def device_on(
    device_id: int,
    request: Request,
    principal: Principal = Depends(require("devices.control")),
) -> dict[str, Any]:
    return await _control(device_id, True, principal, request)


@router.post("/{device_id}/off")
async def device_off(
    device_id: int,
    request: Request,
    principal: Principal = Depends(require("devices.control")),
) -> dict[str, Any]:
    return await _control(device_id, False, principal, request)


async def _control(device_id: int, on: bool, principal: Principal, request: Request) -> dict[str, Any]:
    device = registry.get(device_id)
    if device is None:
        raise HTTPException(status_code=404, detail="Perangkat tidak ditemukan")

    # Per action, not per role: a role may switch a device on and not off.
    if not registry.can_view(principal, device):
        raise HTTPException(status_code=404, detail="Perangkat tidak ditemukan")
    if not registry.can_control(principal, device, "on" if on else "off"):
        raise HTTPException(
            status_code=403,
            detail=f"Tidak berizin {'menyalakan' if on else 'mematikan'} perangkat ini",
        )

    result = await service.run_tuya(controller.controller.set_switch, device, on)
    # A controller that misbehaves must not turn into a 500 for the dashboard:
    # the failure is reported to the user like any other rejected command.
    if not isinstance(result, dict):
        result = {"success": False, "message": "balasan kontrol tidak valid"}

    # A null ACK only means the device accepted the frame; it is not proof the
    # relay moved. Tuya plugs acknowledge well-formed payloads targeting a DP
    # that does not exist, so verify by reading the DP back, with retries —
    # the same approach the reference implementation uses.
    if result.get("success"):
        verified: bool | None = None
        for attempt in range(1, CONTROL_ATTEMPTS + 1):
            await asyncio.sleep(CONTROL_VERIFY_DELAY)
            verified = await service.run_tuya(controller.controller.switch_state, device)
            if verified is on:
                break
            logger.info(
                "[TUYA] %s verifikasi %d/%d: diharapkan %s, terbaca %s",
                device["name"],
                attempt,
                CONTROL_ATTEMPTS,
                on,
                verified,
            )
            if attempt < CONTROL_ATTEMPTS:
                result = await service.run_tuya(controller.controller.set_switch, device, on)
                if not isinstance(result, dict) or not result.get("success"):
                    break

        if verified is not None and verified is not on:
            result = {
                "success": False,
                "message": (
                    f"Perangkat menjawab tetapi saklar tidak berubah "
                    f"(diharapkan {'nyala' if on else 'mati'}). "
                    "Periksa pemetaan DP switch."
                ),
            }

    if result.get("success"):
        state_cache.cache.invalidate(device["name"])
        await state_cache.get_status(device, force=True)
        devices_repo.mark_seen(device_id)
        # Arm only when this role cannot stop the device itself; switching off
        # cancels it. See Watchdog.should_arm.
        from ...telegram import watchdog as watchdog_module

        if on and watchdog_module.watchdog.should_arm(device, principal.role_id):
            watchdog_module.watchdog.arm(device)
        elif not on:
            watchdog_module.watchdog.cancel(device_id)
    else:
        devices_repo.mark_seen(device_id, error=str(result.get("message", "")))

    logs.log_activity(
        device_id=device_id,
        user_id=principal.actor_id,
        actor="ui" if principal.actor_kind == "web" else principal.actor_kind,
        action="turn_on" if on else "turn_off",
        status="success" if result.get("success") else "failed",
        message=str(result.get("message", "")),
    )
    return {
        "success": bool(result.get("success")),
        "message": str(result.get("message", "")),
        "device_id": device_id,
        "state": on if result.get("success") else None,
    }


@router.get("/{device_id}/status")
async def device_status(
    device_id: int,
    principal: Principal = Depends(require("devices.view")),
) -> dict[str, Any]:
    device = _resolve_visible(principal, device_id)
    result = await state_cache.get_status(device)

    payload: dict[str, Any] = {
        "id": device_id,
        "name": device["name"],
        "success": bool(result.get("success")),
        "online": bool(result.get("success")),
    }
    if result.get("success"):
        payload["switch_on"] = result.get("switch_on")
        payload["power_w"] = result.get("power_w")
        payload["current_a"] = result.get("current_a")
        payload["voltage_v"] = result.get("voltage_v")
        payload["age_seconds"] = state_cache.cache.age((device["name"], "status"))
    else:
        payload["message"] = result.get("message", "Gagal membaca status")
    return payload


@router.post("/{device_id}/test")
async def test_device(
    device_id: int,
    principal: Principal = Depends(require("devices.scan")),
) -> dict[str, Any]:
    device = registry.get(device_id)
    if device is None:
        raise HTTPException(status_code=404, detail="Perangkat tidak ditemukan")

    result = await service.run_tuya(controller.controller.test, device)
    if not result.get("success"):
        devices_repo.mark_seen(device_id, error=str(result.get("message", "")))
        return {"success": False, "message": result.get("message", "Perangkat tidak merespons")}

    devices_repo.mark_seen(device_id)
    return {
        "success": True,
        "raw": result.get("raw", {}),
        "mapped": dps_module.extract(device, result.get("raw", {})),
        "dps": device["dps"],
    }


@router.post("/{device_id}/diagnose")
async def diagnose_device(
    device_id: int,
    principal: Principal = Depends(require("devices.scan")),
) -> dict[str, Any]:
    """Reachability report: separates a network problem from a handshake problem."""
    device = registry.get(device_id)
    if device is None:
        raise HTTPException(status_code=404, detail="Perangkat tidak ditemukan")
    return await asyncio.to_thread(diagnostics.diagnose, device)


def _scan_worker(timeout: float) -> dict[str, Any]:
    import tinytuya

    found = tinytuya.deviceScan(verbose=False, maxretry=int(max(1, min(timeout / 2, 20))))
    candidates = []
    for ip, info in (found or {}).items():
        candidates.append(
            {
                "ip": ip,
                "tuya_id": info.get("id"),
                "version": info.get("version"),
                "product_key": info.get("productKey"),
                "name": info.get("name"),
            }
        )
    return {"candidates": candidates}


@router.post("/scan")
async def start_scan(principal: Principal = Depends(require("devices.scan"))) -> dict[str, Any]:
    from ...settings import service as settings_service

    async with _scan_lock:
        running = [job for job in _scan_jobs.values() if job["status"] == "running"]
        if running:
            raise HTTPException(status_code=409, detail="Scan lain sedang berjalan")

        job_id = uuid.uuid4().hex[:8]
        _scan_jobs[job_id] = {"status": "running", "candidates": [], "error": None}
        timeout = settings_service.get_float("tuya.scan_timeout_seconds")

        async def run() -> None:
            try:
                result = await asyncio.wait_for(asyncio.to_thread(_scan_worker, timeout), timeout=timeout)
                _scan_jobs[job_id].update(status="done", candidates=result["candidates"])
            except TimeoutError:
                _scan_jobs[job_id].update(status="error", error="Scan melewati batas waktu")
            except Exception as exc:  # scanning needs the host network; failures are normal
                _scan_jobs[job_id].update(status="error", error=str(exc))

        asyncio.create_task(run())
    return {"job_id": job_id, "status": "running"}


@router.get("/scan/{job_id}")
async def scan_status(
    job_id: str,
    principal: Principal = Depends(require("devices.scan")),
) -> dict[str, Any]:
    job = _scan_jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job scan tidak ditemukan")
    return {"job_id": job_id, **job}
