"""Per-device auto-off watchdog.

Armed when a device with `features.watchdog` is switched on by a role that
cannot switch it off again — a role that can only turn the pump on has no way
to stop it, so the system must. While armed it samples power; if the device
looks idle (a pump with no water) or exceeds the maximum duration, it is
switched off. A role that can switch the device off never arms it.

Cancelled — and not re-armed — while maintenance is on: turning a pump off in
the middle of maintenance is not the intended behaviour.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from ..devices import controller, service
from ..devices import dps as dps_module
from ..infra import state_cache
from ..storage.repos import audit, logs
from ..storage.repos import devices as devices_repo

logger = logging.getLogger(__name__)

DEFAULTS = {
    "watchdog.idle_watt": 200.0,
    "watchdog.check_minutes": 3,
    "watchdog.max_minutes": 30,
    "watchdog.sample_count": 3,
    "watchdog.sample_delay_seconds": 2.0,
}


class Watchdog:
    def __init__(self) -> None:
        self._tasks: dict[int, asyncio.Task] = {}
        self._state: dict[int, dict[str, Any]] = {}

    def _setting(self, device_id: int, key: str) -> Any:
        return devices_repo.get_setting(device_id, key, DEFAULTS[key])

    def should_arm(self, device: dict[str, Any], role_id: int | None) -> bool:
        """Arm when the actor cannot switch the device off themselves.

        This mirrors the reference: a role that can only switch the pump on has
        no way to stop it, so the system must. A role that can switch it off is
        trusted to do so, and no watchdog runs. Deriving the rule from the
        permission means it cannot drift out of sync with it.
        """
        if not dps_module.has_feature(device, "watchdog"):
            return False
        if role_id is None:
            return False
        # Reuse the same function the control paths use, so the two can never
        # disagree: it already accounts for manage_devices and for the
        # per-device row.
        from ..devices import registry

        return not registry.can_control(_RolePrincipal(role_id), device, "off")

    def arm(self, device: dict[str, Any]) -> None:
        from ..maintenance import service as maintenance_service

        if maintenance_service.is_on():
            logger.info("[WATCHDOG] maintenance aktif; tidak mengarm %s", device["name"])
            return
        self.cancel(device["id"])
        task = asyncio.create_task(self._loop(device), name=f"watchdog:{device['name']}")
        self._tasks[device["id"]] = task
        self._state[device["id"]] = {"running": True, "device": device["name"]}

    def cancel(self, device_id: int) -> bool:
        task = self._tasks.pop(device_id, None)
        self._state.pop(device_id, None)
        if task is not None and not task.done():
            task.cancel()
            return True
        return False

    def cancel_all(self) -> None:
        for device_id in list(self._tasks):
            self.cancel(device_id)

    def status(self) -> dict[int, dict[str, Any]]:
        return dict(self._state)

    async def _loop(self, device: dict[str, Any]) -> None:
        try:
            check_minutes = float(self._setting(device["id"], "watchdog.check_minutes"))
            max_minutes = float(self._setting(device["id"], "watchdog.max_minutes"))
            idle_watt = float(self._setting(device["id"], "watchdog.idle_watt"))
            sample_count = max(1, int(self._setting(device["id"], "watchdog.sample_count")))
            delay = float(self._setting(device["id"], "watchdog.sample_delay_seconds"))

            elapsed = 0.0
            while True:
                await asyncio.sleep(check_minutes * 60)
                elapsed += check_minutes

                status = await state_cache.get_status(device, force=True)
                if not status.get("success"):
                    continue
                if not status.get("switch_on"):
                    return  # already off; nothing to watch

                if elapsed >= max_minutes:
                    await self._switch_off(device, f"melewati batas {max_minutes:.0f} menit")
                    return

                samples = []
                for index in range(sample_count):
                    reading = await state_cache.get_status(device, force=True)
                    if reading.get("success") and isinstance(reading.get("power_w"), (int, float)):
                        samples.append(float(reading["power_w"]))
                    if index + 1 < sample_count:
                        await asyncio.sleep(max(0.01, delay))

                if samples and max(samples) < idle_watt:
                    await self._switch_off(device, f"idle di bawah {idle_watt:.0f}W")
                    return
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("[WATCHDOG] loop gagal untuk %s", device["name"])
        finally:
            self._state.pop(device["id"], None)

    async def _switch_off(self, device: dict[str, Any], reason: str) -> None:
        result = await service.run_tuya(controller.controller.set_switch, device, False)
        state_cache.cache.invalidate(device["name"])

        logs.log_activity(
            device_id=device["id"],
            user_id=None,
            actor="system",
            action="watchdog_off",
            status="success" if result.get("success") else "failed",
            message=reason,
        )
        audit.write(
            "system",
            None,
            "watchdog",
            "device.watchdog_off",
            target_kind="device",
            target_id=device["id"],
            details={"reason": reason, "success": bool(result.get("success"))},
        )
        logger.warning("[WATCHDOG] %s dimatikan otomatis: %s", device["name"], reason)


def sync_after_control(dog: Watchdog, device: dict[str, Any], on: bool, role_id: int | None) -> None:
    """Keep the watchdog in step with a switch command that just succeeded.

    An off command always cancels: the pump is off, so there is nothing left to
    auto-off, and a stale task would fire later for no reason. An on command
    arms only when this role cannot switch it off; a role that can switch it off
    cancels instead, so a watchdog armed by an earlier, less privileged actor
    does not outlive the person who is now in control.
    """
    if not on:
        dog.cancel(device["id"])
    elif dog.should_arm(device, role_id):
        dog.arm(device)
    else:
        dog.cancel(device["id"])


class _RolePrincipal:
    """Minimal principal for a permission check that needs only a role."""

    def __init__(self, role_id: int) -> None:
        self.role_id = role_id


watchdog = Watchdog()
