"""Entry point: one process runs uvicorn, the Telegram bots, and the scheduler.

One process is deliberate: a single owner of device I/O and the state cache.
Splitting the API from the bots would mean two processes racing for the same
Tuya sockets.
"""

from __future__ import annotations

import asyncio
import logging
import sys
from typing import Any

import uvicorn

from . import bootstrap, config
from .backup import service as backup_service
from .devices import registry
from .devices import service as device_service
from .infra import asyncdb, state_cache
from .infra.scheduler import Scheduler
from .settings import service as settings_service
from .storage import db
from .storage.repos import logs
from .telegram import manager as bot_manager_module
from .web.app import create_app

logger = logging.getLogger(__name__)


async def _power_snapshot() -> None:
    from .devices import dps

    for device in registry.all_devices():
        if not dps.has_feature(device, "power_logging") or not registry_devices_power(device):
            continue
        result = await state_cache.get_status(device)
        if not result.get("success"):
            continue
        await asyncdb.run_db(
            logs.log_power,
            device_id=device["id"],
            power_w=float(result.get("power_w") or 0),
            voltage_v=float(result.get("voltage_v") or 0),
            current_a=float(result.get("current_a") or 0),
            switch_state=result.get("switch_on"),
            source="periodic",
        )


def registry_devices_power(device: dict[str, Any]) -> bool:
    from .devices import dps

    return dps.supports_power(device)


async def _warm_cache() -> None:
    for device in registry.all_devices():
        await state_cache.get_status(device)


async def _housekeeping() -> None:
    result = await asyncdb.run_db(
        logs.cleanup,
        settings_service.get_int("housekeeping.log_retention_days"),
        settings_service.get_int("housekeeping.audit_retention_days"),
    )
    logger.info("[HOUSEKEEPING] %s", result)


async def _backup() -> None:
    if not settings_service.get_bool("backup.auto_enabled"):
        return
    result = await asyncdb.run_db(backup_service.create, "auto")
    await asyncdb.run_db(backup_service.prune)
    logger.info("[BACKUP] %s", result["filename"])


def _session_sweep() -> int:
    from .access import rate_limit, sessions

    removed = sessions.sweep()
    rate_limit.prune(settings_service.get_int("security.rate_limit_window_seconds") * 2)
    return removed


def build_scheduler() -> Scheduler:
    from .devices import controller as controller_module  # noqa: F401 - ensure import side effects

    scheduler = Scheduler()
    scheduler.add_job(
        "cache-warm",
        max(15.0, settings_service.get_float("monitoring.warm_interval_seconds")),
        _warm_cache,
        initial_delay=5,
    )
    scheduler.add_job(
        "power-snapshot",
        max(60.0, settings_service.get_int("monitoring.power_interval_minutes") * 60.0),
        _power_snapshot,
        initial_delay=20,
    )
    scheduler.add_job(
        "housekeeping",
        max(1.0, settings_service.get_int("housekeeping.interval_hours") * 3600.0),
        _housekeeping,
        initial_delay=3600,
    )
    scheduler.add_job(
        "backup",
        max(1.0, settings_service.get_int("backup.interval_hours") * 3600.0),
        _backup,
        initial_delay=900,
    )
    scheduler.add_job("session-sweep", 3600, _session_sweep, initial_delay=60)
    return scheduler


def _apply_runtime_settings(_: dict[str, Any] | None = None) -> None:
    """Re-read values that live outside the settings cache itself."""
    device_service.configure(
        settings_service.get_int("tuya.threads"),
        settings_service.get_float("tuya.call_timeout_seconds"),
    )


async def run() -> None:
    settings = config.load()
    schema_version = bootstrap.init(settings)
    _apply_runtime_settings()
    settings_service.subscribe(_apply_runtime_settings)

    from .storage.repos import app_state

    app_state.set("schema_version", schema_version)
    app_state.set("data_dir", str(settings.data_dir))
    # `system.*` settings are read-only by design: they reflect process state,
    # not operator configuration. Mirror them for the settings UI without
    # writing through the validated (and therefore rejecting) patch path.
    settings_service.prime_read_only(
        {"system.schema_version": schema_version, "system.data_dir": str(settings.data_dir)}
    )

    if not app_state.is_setup_complete():
        logger.info("Belum ada setup. Buka dashboard dan selesaikan wizard terlebih dahulu.")

    registry.reload()

    app = create_app()
    server = uvicorn.Server(
        uvicorn.Config(app, host=settings.api_host, port=settings.api_port, log_level="info")
    )

    scheduler = build_scheduler()
    scheduler.start()

    manager = bot_manager_module.manager
    try:
        await manager.start_all()
    except Exception:
        logger.exception("[TELEGRAM] gagal memulai bot; API tetap jalan")

    logger.info("API dashboard: http://%s:%s", settings.api_host, settings.api_port)
    try:
        await server.serve()
    finally:
        await manager.shutdown()
        await scheduler.stop()
        from .telegram import watchdog as watchdog_module

        watchdog_module.watchdog.cancel_all()
        asyncdb.shutdown()
        device_service.shutdown()
        db.close_all()
        logger.info("Shutdown selesai.")


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("telegram").setLevel(logging.INFO)
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        pass
    except Exception:
        logger.exception("Aplikasi berhenti karena error")
        sys.exit(1)


if __name__ == "__main__":
    main()
