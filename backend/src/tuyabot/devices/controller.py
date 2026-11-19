"""tinytuya controller: lazy clients, one lock per device.

A client is created on first use and reused. Changing a device's IP, key, or
version calls `forget()` so the next call rebuilds it — no restart needed.
"""

from __future__ import annotations

import logging
import threading
from typing import Any

import tinytuya

from . import dps as dps_module

logger = logging.getLogger(__name__)

SOCKET_TIMEOUT = 4
RETRY_LIMIT = 2
RETRY_DELAY = 0.5


def _describe_target(device: dict) -> str:
    """Everything needed to diagnose reachability, without the local key."""
    return (
        f"ip={device.get('ip') or '-'} "
        f"id={device.get('tuya_id') or '-'} "
        f"version={device.get('version') or '-'} "
        f"key={'set' if device.get('local_key') else 'MISSING'}"
    )


class TuyaController:
    def __init__(self) -> None:
        self._entries: dict[int, dict[str, Any]] = {}
        self._lock = threading.Lock()

    def _entry(self, device: dict) -> dict[str, Any]:
        device_id = device["id"]
        with self._lock:
            entry = self._entries.get(device_id)
            if entry is not None:
                return entry
            if not device.get("ip") and not device.get("tuya_id"):
                raise RuntimeError("perangkat belum punya IP atau ID")
            client = tinytuya.Device(
                dev_id=device["tuya_id"],
                address=device.get("ip") or "Auto",
                local_key=device["local_key"],
                version=float(device.get("version") or 3.5),
            )
            client.set_socketTimeout(SOCKET_TIMEOUT)
            client.set_socketRetryLimit(RETRY_LIMIT)
            client.set_socketRetryDelay(RETRY_DELAY)
            # Persistent sockets return stale cached status; always read fresh.
            client.set_socketPersistent(False)
            entry = {"client": client, "lock": threading.Lock(), "signature": self._signature(device)}
            self._entries[device_id] = entry
            # One line per new client: without it a failing control leaves no
            # trace at all, because an unreachable device returns None instead
            # of raising. See _describe_target().
            logger.info(
                "[TUYA] klien dibuat untuk %s -> %s",
                device.get("name"),
                _describe_target(device),
            )
            return entry

    @staticmethod
    def _signature(device: dict) -> tuple:
        return (device.get("tuya_id"), device.get("ip"), device.get("local_key"), device.get("version"))

    def forget(self, device_id: int) -> None:
        with self._lock:
            self._entries.pop(device_id, None)

    def forget_all(self) -> None:
        with self._lock:
            self._entries.clear()

    def _call(self, device: dict, action) -> dict[str, Any]:
        try:
            entry = self._entry(device)
        except Exception as exc:
            return {"success": False, "message": f"Gagal menyiapkan perangkat: {exc}"}

        with entry["lock"]:
            try:
                return action(entry["client"])
            except Exception as exc:  # network errors, bad local key, timeouts
                logger.warning("[TUYA] %s gagal: %s", device.get("name"), exc)
                self.forget(device["id"])
                # A raised socket/timeout error means the device did not answer.
                return {"success": False, "message": str(exc), "unreachable": True}

    def status(self, device: dict) -> dict[str, Any]:
        def action(client):
            raw = client.status()
            if raw is None:
                # Unlike a control ACK, a status request must carry payload;
                # None here means the device sent nothing usable.
                logger.warning(
                    "[TUYA] %s tidak mengirim status (%s)",
                    device.get("name"),
                    _describe_target(device),
                )
                return {"success": False, "message": "perangkat tidak mengirim status"}
            if not isinstance(raw, dict) or raw.get("Error"):
                logger.warning(
                    "[TUYA] %s status gagal: %r (%s)",
                    device.get("name"),
                    raw if not isinstance(raw, dict) else raw.get("Error"),
                    _describe_target(device),
                )
                return {"success": False, "message": str(raw.get("Error") if isinstance(raw, dict) else raw)}
            raw_dps = raw.get("dps", raw)
            return {"success": True, "raw": raw_dps, **dps_module.extract(device, raw_dps)}

        return self._call(device, action)

    def set_switch(self, device: dict, on: bool) -> dict[str, Any]:
        index = dps_module.switch_index(device)
        if index is None:
            return {"success": False, "message": "perangkat tidak punya DP switch"}

        def action(client):
            # tinytuya's signature is set_status(on, switch=1, nowait=False):
            # the VALUE comes first and the DP index second. Calling it as
            # set_status(index, on) inverted them, so the command targeted DP
            # "True"/"False" instead of DP 1. The device still answered with a
            # null ACK because the payload was well-formed, so every toggle
            # reported success while the pump never changed. Named arguments
            # here make the order impossible to get wrong again.
            raw = client.set_status(on=bool(on), switch=index)
            # A null ACK means "accepted", not "applied". The reference
            # implementation never trusts it: it re-reads the DP and retries.
            # So this only reports a transport-level problem; _control verifies
            # the resulting state before claiming success.
            if raw is None:
                return {"success": True, "ack": "null"}
            if not isinstance(raw, dict):
                logger.warning("[TUYA] %s balasan tak dikenal: %r", device.get("name"), raw)
                return {"success": False, "message": f"balasan tak dikenal: {raw!r}"}
            if raw.get("Error") or raw.get("Err"):
                message = raw.get("Error") or raw.get("Err")
                unreachable = str(message).lower() in {
                    "network error", "device not found", "connect failed",
                } or "network" in str(message).lower()
                logger.warning(
                    "[TUYA] %s menolak perintah: %s (%s)",
                    device.get("name"),
                    message,
                    _describe_target(device),
                )
                return {"success": False, "message": str(message), "unreachable": unreachable}
            return {"success": True}

        return self._call(device, action)

    def switch_state(self, device: dict) -> bool | None:
        """Read the switch DP back; None when it cannot be determined."""
        result = self.status(device)
        if not result.get("success"):
            return None
        return result.get("switch_on")

    def test(self, device: dict) -> dict[str, Any]:
        return self.status(device)

    def shutdown(self) -> None:
        self.forget_all()


controller = TuyaController()
