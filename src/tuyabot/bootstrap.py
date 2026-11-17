"""Process bootstrap: data directory, session secret, database, migrations."""

from __future__ import annotations

import contextlib
import logging
import os
import secrets
import stat
from pathlib import Path

from .config import Settings
from .storage import db, migrate

logger = logging.getLogger(__name__)

SECRET_FILE = "secret.key"


def ensure_data_dir(data_dir: Path) -> None:
    data_dir.mkdir(parents=True, exist_ok=True)
    with contextlib.suppress(OSError):
        os.chmod(data_dir, stat.S_IRWXU)  # 0700


def load_or_create_secret(data_dir: Path) -> bytes:
    """Session signing secret. Not part of DB backups: a move to another machine
    rotates it, which invalidates every old session — the desired behaviour."""
    path = data_dir / SECRET_FILE
    if path.exists():
        return path.read_bytes()
    data_dir.mkdir(parents=True, exist_ok=True)
    secret = secrets.token_bytes(32)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        os.write(fd, secret)
    finally:
        os.close(fd)
    logger.info("Secret sesi baru dibuat: %s", path)
    return secret


_secret: bytes = b""


def secret() -> bytes:
    return _secret


def init(settings: Settings) -> int:
    """Create dirs, secret, connect the DB, run migrations. Returns schema version."""
    global _secret
    ensure_data_dir(settings.data_dir)
    for sub in ("backups", "logs"):
        (settings.data_dir / sub).mkdir(parents=True, exist_ok=True)

    _secret = load_or_create_secret(settings.data_dir)

    db_path = str(settings.data_dir / "tuyabot.db")
    db.configure(db_path)
    version = migrate.apply()
    logger.info("Database siap: %s (schema v%d, generation %d)", db_path, version, db.current_generation())
    return version
