"""Cache TTL, single-flight, and failure TTL."""

import asyncio
import time

import pytest

from tuyabot.devices import controller as controller_module
from tuyabot.infra import state_cache
from tuyabot.settings import service as settings_service


@pytest.fixture()
def counting(ready_db, monkeypatch):
    calls = {"n": 0}

    def status(device):
        calls["n"] += 1
        return {"success": True, "switch_on": True, "raw": {}}

    monkeypatch.setattr(controller_module.controller, "status", status)
    settings_service.patch(
        {"monitoring.cache_ttl_seconds": 5.0, "monitoring.error_ttl_seconds": 1.0}, actor={}
    )
    state_cache.cache._entries.clear()
    return calls


def test_second_read_comes_from_cache(counting):
    device = {"id": 1, "name": "air", "dps": {"switch": 1}}
    asyncio.run(state_cache.get_status(device))
    asyncio.run(state_cache.get_status(device))
    assert counting["n"] == 1


def test_force_bypasses_cache(counting):
    device = {"id": 1, "name": "air", "dps": {"switch": 1}}
    asyncio.run(state_cache.get_status(device))
    asyncio.run(state_cache.get_status(device, force=True))
    assert counting["n"] == 2


def test_concurrent_readers_trigger_one_call(counting):
    device = {"id": 1, "name": "air", "dps": {"switch": 1}}

    async def fire():
        return await asyncio.gather(*[state_cache.get_status(device) for _ in range(10)])

    asyncio.run(fire())
    assert counting["n"] == 1


def test_error_ttl_is_shorter(ready_db, monkeypatch):
    calls = {"n": 0}

    def failing(device):
        calls["n"] += 1
        return {"success": False, "message": "offline"}

    monkeypatch.setattr(controller_module.controller, "status", failing)
    settings_service.patch(
        {"monitoring.cache_ttl_seconds": 30.0, "monitoring.error_ttl_seconds": 0.5}, actor={}
    )
    state_cache.cache._entries.clear()
    device = {"id": 1, "name": "air", "dps": {"switch": 1}}

    asyncio.run(state_cache.get_status(device))
    time.sleep(0.6)
    asyncio.run(state_cache.get_status(device))
    assert calls["n"] == 2


def test_invalidate_by_device_name(counting):
    device = {"id": 1, "name": "air", "dps": {"switch": 1}}
    asyncio.run(state_cache.get_status(device))
    state_cache.cache.invalidate("air")
    asyncio.run(state_cache.get_status(device))
    assert counting["n"] == 2


def test_age_reflects_elapsed_time(counting):
    device = {"id": 1, "name": "air", "dps": {"switch": 1}}
    asyncio.run(state_cache.get_status(device))
    time.sleep(0.05)
    assert state_cache.cache.age(("air", "status")) >= 0.05
