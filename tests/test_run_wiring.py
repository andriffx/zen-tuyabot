"""Wiring: the entry point starts bots, scheduler, and applies settings."""

import inspect

from tuyabot import main


def test_build_scheduler_registers_every_job():
    names = {job.name for job in main.build_scheduler().jobs}
    assert names == {"cache-warm", "power-snapshot", "housekeeping", "backup", "session-sweep"}


def test_backup_job_does_not_wait_a_full_interval():
    backup = next(job for job in main.build_scheduler().jobs if job.name == "backup")
    assert backup.initial_delay == 900


def test_runtime_settings_configure_device_layer(ready_db):
    from tuyabot.devices import service as device_service
    from tuyabot.settings import service as settings_service

    settings_service.patch(
        {"tuya.threads": 6, "tuya.call_timeout_seconds": 12.0}, actor={}
    )
    main._apply_runtime_settings()
    assert device_service._threads == 6
    assert device_service._default_timeout == 12.0


def test_entry_point_is_async_main():
    assert inspect.iscoroutinefunction(main.run)


def test_power_snapshot_skips_devices_without_power(ready_db, monkeypatch):
    """A bulb with no power DP must not create empty power rows."""
    import asyncio

    from tuyabot.devices import registry
    from tuyabot.storage.repos import devices as devices_repo
    from tuyabot.storage.repos import logs

    devices_repo.create(
        {"name": "lampu", "label": "Lampu", "tuya_id": "p1", "local_key": "k", "type": "bulb",
         "features": {"power_logging": True}}
    )
    registry.reload()

    called = {"n": 0}

    async def fake_status(device, force=False):
        called["n"] += 1
        return {"success": True, "power_w": 1.0}

    monkeypatch.setattr("tuyabot.infra.state_cache.get_status", fake_status)
    asyncio.run(main._power_snapshot())
    assert called["n"] == 0
    assert logs.recent_power() == []
    registry.reset_cache()
