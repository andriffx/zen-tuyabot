"""Stats and health snapshots."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from ...infra import state_cache
from .. import db, migrate
from . import backup_runs, logs
from . import devices as devices_repo


def stats() -> dict[str, Any]:
    devices = devices_repo.list_all(active_only=True)
    online = 0
    for device in devices:
        entry = state_cache.cache.read((device["name"], "status"))
        if entry and entry.get("success"):
            online += 1

    path = Path(db.path())
    size = path.stat().st_size if path.exists() else 0
    last = backup_runs.last()

    return {
        "devices": {"total": len(devices), "online": online, "offline": len(devices) - online},
        "rows": logs.count_rows(),
        "database": {
            "path": str(path),
            "size_bytes": size,
            "schema_version": migrate.current_version(),
        },
        "backup": {"last": last["filename"] if last else None, "last_at": last["created_at"] if last else None},
        "process": {"pid": os.getpid()},
    }


def health() -> dict[str, Any]:
    from ...maintenance import service as maintenance_service

    db_ok = db.ping()
    devices = devices_repo.list_all(active_only=True)
    fresh = 0
    for device in devices:
        age = state_cache.cache.age((device["name"], "status"))
        if age is not None and age < 300:
            fresh += 1

    if db_ok and (fresh or not devices):
        status = "ok"
    elif db_ok:
        status = "degraded"
    else:
        status = "down"

    return {
        "status": status,
        "database": db_ok,
        "devices_total": len(devices),
        "devices_fresh": fresh,
        "maintenance": maintenance_service.is_on(),
    }
