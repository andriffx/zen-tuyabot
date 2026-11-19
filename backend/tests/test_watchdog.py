"""Watchdog: idles off, max duration off, normal run continues, cancel, maintenance."""

import asyncio

import pytest

from tuyabot.devices import controller as controller_module
from tuyabot.devices import registry
from tuyabot.maintenance import service as maintenance_service
from tuyabot.storage.repos import devices as devices_repo
from tuyabot.storage.repos import logs
from tuyabot.telegram import watchdog as watchdog_module


@pytest.fixture()
def wide_device(ready_db):
    device_id = devices_repo.create(
        {
            "name": "pompa",
            "label": "Pompa",
            "tuya_id": "w1",
            "local_key": "k",
            "type": "plug",
            "features": {"watchdog": True},
        }
    )
    registry.reload()
    device = registry.get(device_id)

    # Settings small enough for a fast test.
    devices_repo.set_setting(device_id, "watchdog.check_minutes", 0.001)
    devices_repo.set_setting(device_id, "watchdog.max_minutes", 60)
    devices_repo.set_setting(device_id, "watchdog.idle_watt", 200)
    devices_repo.set_setting(device_id, "watchdog.sample_count", 2)
    devices_repo.set_setting(device_id, "watchdog.sample_delay_seconds", 0.001)
    yield device
    registry.reset_cache()


@pytest.fixture()
def tuya_state(monkeypatch):
    state = {"power": 500.0, "on": True, "off_calls": 0}

    async def status(device, force=False):
        return {"success": True, "switch_on": state["on"], "power_w": state["power"]}

    def set_switch(device, on):
        if not on:
            state["off_calls"] += 1
            state["on"] = False
        return {"success": True}

    monkeypatch.setattr("tuyabot.infra.state_cache.get_status", status)
    monkeypatch.setattr(controller_module.controller, "set_switch", set_switch)
    return state


def _run_with(dog, device, seconds: float = 0.3) -> None:
    """Arm and let the loop run inside one event loop (create_task needs one)."""

    async def scenario():
        dog.arm(device)
        await asyncio.sleep(seconds)

    asyncio.run(scenario())


def test_idle_device_is_switched_off(wide_device, tuya_state):
    tuya_state["power"] = 10.0
    dog = watchdog_module.Watchdog()
    _run_with(dog, wide_device)
    assert tuya_state["off_calls"] >= 1

    rows = logs.recent_activities(device_id=wide_device["id"])
    assert rows[0]["action"] == "watchdog_off"
    assert rows[0]["actor"] == "system"


def test_active_device_is_left_on(wide_device, tuya_state):
    tuya_state["power"] = 900.0
    dog = watchdog_module.Watchdog()
    _run_with(dog, wide_device)
    assert tuya_state["off_calls"] == 0


def test_max_duration_switches_off(wide_device, tuya_state):
    devices_repo.set_setting(wide_device["id"], "watchdog.max_minutes", 0.001)
    tuya_state["power"] = 900.0
    dog = watchdog_module.Watchdog()
    _run_with(dog, wide_device)
    assert tuya_state["off_calls"] >= 1


def test_cancel_stops_watching(wide_device, tuya_state):
    tuya_state["power"] = 10.0
    dog = watchdog_module.Watchdog()

    async def scenario():
        dog.arm(wide_device)
        dog.cancel(wide_device["id"])
        await asyncio.sleep(0.3)

    asyncio.run(scenario())
    assert tuya_state["off_calls"] == 0


def test_maintenance_prevents_arming(wide_device, tuya_state, ready_db):
    maintenance_service.enable("uji")
    tuya_state["power"] = 10.0
    dog = watchdog_module.Watchdog()
    _run_with(dog, wide_device)
    assert tuya_state["off_calls"] == 0
    assert dog.status() == {}
    maintenance_service.disable()


def test_should_arm_follows_the_ability_to_switch_off(ready_db):
    device_id = devices_repo.create(
        {
            "name": "pompa2",
            "label": "Pompa 2",
            "tuya_id": "w2",
            "local_key": "k",
            "type": "plug",
            "features": {"watchdog": True},
        }
    )
    registry.reload()
    device = registry.get(device_id)
    dog = watchdog_module.Watchdog()

    from tuyabot.storage.repos import role_devices, roles

    # A role that can only switch the pump on has no way to stop it, so the
    # watchdog arms. A role that can switch it off is trusted to do so.
    on_only = roles.create("ononly", "On only", None, [])
    role_devices.set_for_role(
        on_only, [{"device_id": device_id, "can_view": True, "can_on": True, "can_off": False}]
    )
    full = roles.create("full", "Full", None, [])
    role_devices.set_for_role(
        full, [{"device_id": device_id, "can_view": True, "can_on": True, "can_off": True}]
    )

    assert dog.should_arm(device, on_only) is True
    assert dog.should_arm(device, full) is False
    registry.reset_cache()


def test_device_without_feature_never_arms(ready_db):
    device_id = devices_repo.create(
        {"name": "lampu", "label": "Lampu", "tuya_id": "w3", "local_key": "k", "type": "bulb"}
    )
    registry.reload()
    device = registry.get(device_id)
    assert watchdog_module.Watchdog().should_arm(device, "operator") is False
    registry.reset_cache()
