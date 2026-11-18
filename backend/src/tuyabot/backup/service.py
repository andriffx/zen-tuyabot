"""Backup and atomic restore.

Restore order (spec §8.19) is the whole point of this module: verify, migrate a
copy, back up the current DB, copy the contents into the live file, bump the
generation, reset caches, rebuild bots. A failure at any stage leaves the old
database usable and maintenance on.
"""

from __future__ import annotations

import logging
import os
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from ..bootstrap import SECRET_FILE  # noqa: F401 - documents what is NOT backed up
from ..settings import service as settings_service
from ..storage import db, migrate
from ..storage.repos import audit, backup_runs

logger = logging.getLogger(__name__)


class RestoreError(RuntimeError):
    def __init__(self, stage: str, message: str) -> None:
        super().__init__(message)
        self.stage = stage
        self.message = message


def backups_dir() -> Path:
    return Path(db.path()).parent / "backups"


def create(kind: str = "manual", note: str | None = None) -> dict[str, Any]:
    """Consistent copy via VACUUM INTO; the bot keeps running."""
    directory = backups_dir()
    directory.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    filename = f"tuyabot-{stamp}.db"
    target = directory / filename
    if target.exists():
        target = directory / f"tuyabot-{stamp}-{os.getpid()}.db"

    with db.raw_connection() as cur:
        cur.execute("VACUUM INTO ?", (str(target),))
    os.chmod(target, 0o600)

    run_id = backup_runs.record(filename, target.stat().st_size, kind, note)
    logger.info("[BACKUP] %s dibuat (%s bytes)", filename, target.stat().st_size)
    return {"id": run_id, "filename": filename, "path": str(target), "size_bytes": target.stat().st_size}


def prune() -> int:
    retention = settings_service.get_int("backup.retention_days")
    removed = 0
    directory = backups_dir()
    if not directory.exists():
        return 0
    for path in directory.glob("tuyabot-*.db"):
        age_days = (datetime.now() - datetime.fromtimestamp(path.stat().st_mtime)).days
        if age_days > retention:
            path.unlink(missing_ok=True)
            backup_runs.forget(path.name)
            removed += 1
    return removed


def _verify_integrity(path: Path) -> None:
    """Open the uploaded file standalone and check it is a valid SQLite DB."""
    try:
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        try:
            result = conn.execute("PRAGMA integrity_check").fetchone()
            if not result or result[0] != "ok":
                raise RestoreError(
                    "integrity", f"integrity_check gagal: {result[0] if result else 'kosong'}"
                )
            tables = {
                row[0]
                for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
            }
        finally:
            conn.close()
    except RestoreError:
        raise
    except sqlite3.DatabaseError as exc:
        raise RestoreError("integrity", f"Bukan database SQLite yang valid: {exc}") from exc

    required = {"roles", "web_users", "devices", "app_state"}
    missing = required - tables
    if missing:
        raise RestoreError("schema", f"bukan database tuyabot: tabel hilang {', '.join(sorted(missing))}")


def _schema_version(path: Path) -> int:
    try:
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        try:
            row = conn.execute("SELECT MAX(version) FROM schema_migrations").fetchone()
            return int(row[0] or 0)
        finally:
            conn.close()
    except sqlite3.DatabaseError as exc:
        raise RestoreError("schema", f"Tidak bisa membaca schema_migrations: {exc}") from exc


def _migrate_copy(path: Path, target_version: int, source_version: int) -> None:
    """Bring an older backup up to the current schema before swapping it in."""
    if source_version >= target_version:
        return
    original_path, timeout = db.path(), settings_service.get_int("security.rate_limit_window_seconds")
    db.configure(str(path), busy_timeout_ms=max(1000, timeout * 1000))
    try:
        migrate.apply()
    finally:
        db.configure(original_path)


def restore(upload_path: Path, *, backup_kind: str = "pre_restore") -> dict[str, Any]:
    """Replace the live database with `upload_path`. Raises RestoreError."""
    from ..devices import registry
    from ..infra import state_cache

    upload_path = Path(upload_path)
    if not upload_path.exists():
        raise RestoreError("upload", "File backup tidak ditemukan")

    _verify_integrity(upload_path)

    current_version = migrate.available()[-1][0]
    incoming_version = _schema_version(upload_path)
    if incoming_version > current_version:
        raise RestoreError(
            "version",
            f"Backup dari versi skema {incoming_version}, aplikasi ini mendukung maksimal {current_version}",
        )

    _migrate_copy(upload_path, current_version, incoming_version)

    pre = create(kind=backup_kind, note=f"sebelum restore dari {upload_path.name}")

    try:
        # In-place copy, not a file swap: other threads (request pool, scheduler,
        # bots) hold open connections that cannot be closed from here. See
        # db.restore_in_place.
        db.restore_in_place(upload_path)
    except Exception as exc:
        raise RestoreError("swap", f"Gagal menukar isi database: {exc}") from exc

    db.bump_generation()
    settings_service.reset_cache()
    app_state_reset()
    state_cache.cache.clear()
    registry.reset_cache()

    # The swapped-in file carries the backup_runs table as it was when it was
    # taken, so the pre_restore record written above no longer exists. Re-register
    # the file we just saved so the operator can see (and download) the safety copy.
    backup_runs.record(
        Path(pre["path"]).name,
        pre["size_bytes"],
        backup_kind,
        f"sebelum restore dari {upload_path.name}",
    )

    audit.write(
        "system",
        None,
        "restore",
        "backup.restore",
        target_kind="backup",
        target_id=pre["filename"],
        details={"source": upload_path.name, "from_version": incoming_version, "to_version": current_version},
    )
    return {
        "restored": True,
        "from_version": incoming_version,
        "schema_version": current_version,
        "pre_restore_backup": pre["filename"],
    }


def app_state_reset() -> None:
    from ..storage.repos import app_state

    app_state.reset_cache()
