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
                return {"success": False, "message": str(exc)}

    def status(self, device: dict) -> dict[str, Any]:
        def action(client):
            raw = client.status()
            if not isinstance(raw, dict) or raw.get("Error"):
                return {"success": False, "message": str(raw.get("Error") if isinstance(raw, dict) else raw)}
            raw_dps = raw.get("dps", raw)
            return {"success": True, "raw": raw_dps, **dps_module.extract(device, raw_dps)}

        return self._call(device, action)

    def set_switch(self, device: dict, on: bool) -> dict[str, Any]:
        index = dps_module.switch_index(device)
        if index is None:
            return {"success": False, "message": "perangkat tidak punya DP switch"}
        return self._call(device, lambda client: client.set_status(index, bool(on)))

    def test(self, device: dict) -> dict[str, Any]:
        return self.status(device)

    def shutdown(self) -> None:
        self.forget_all()


controller = TuyaController()
