"""Device state cache with TTL and single-flight.

A dashboard, a bot, and a scheduler may all want the same reading. With this
cache they cause one device call per TTL, not one each. Failures get a shorter
TTL so an offline device is not hammered by retries.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

from ..devices import controller, service
from ..settings import service as settings_service

Key = tuple[str, str]


class DeviceStateCache:
    def __init__(self) -> None:
        self._entries: dict[Key, tuple[float, dict[str, Any]]] = {}
        self._locks: dict[Key, asyncio.Lock] = {}

    def _ttl(self) -> float:
        return settings_service.get_float("monitoring.cache_ttl_seconds")

    def _error_ttl(self) -> float:
        return settings_service.get_float("monitoring.error_ttl_seconds")

    def _lock(self, key: Key) -> asyncio.Lock:
        lock = self._locks.get(key)
        if lock is None:
            lock = asyncio.Lock()
            self._locks[key] = lock
        return lock

    def _fresh(self, key: Key) -> dict[str, Any] | None:
        entry = self._entries.get(key)
        if entry is None:
            return None
        stamp, value = entry
        ttl = self._ttl() if value.get("success") else self._error_ttl()
        if time.monotonic() - stamp <= ttl:
            return value
        return None

    def read(self, key: Key) -> dict[str, Any] | None:
        entry = self._entries.get(key)
        return entry[1] if entry else None

    def age(self, key: Key) -> float | None:
        entry = self._entries.get(key)
        return time.monotonic() - entry[0] if entry else None

    def invalidate(self, device_name: str) -> None:
        for key in [k for k in self._entries if k[0] == device_name]:
            self._entries.pop(key, None)

    def clear(self) -> None:
        self._entries.clear()
        self._locks.clear()

    async def get(self, device: dict[str, Any], kind: str, *, force: bool = False) -> dict[str, Any]:
        key = (device["name"], kind)
        if not force:
            cached = self._fresh(key)
            if cached is not None:
                return cached

        async with self._lock(key):
            if not force:
                cached = self._fresh(key)
                if cached is not None:
                    return cached

            if kind == "status" or kind == "power":
                result = await service.run_tuya(controller.controller.status, device)
            else:
                raise ValueError(f"jenis cache tidak dikenal: {kind}")

            self._entries[key] = (time.monotonic(), result)
            return result

    def snapshot(self) -> dict[Key, dict[str, Any]]:
        return dict(self._entries)


cache = DeviceStateCache()


async def get_status(device: dict[str, Any], *, force: bool = False) -> dict[str, Any]:
    return await cache.get(device, "status", force=force)


async def get_power(device: dict[str, Any], *, force: bool = False) -> dict[str, Any]:
    return await cache.get(device, "power", force=force)
