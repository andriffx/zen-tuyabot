"""Numbered SQL migration runner with checksum verification."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

from . import db

MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"
FILENAME_RE = re.compile(r"^(\d{4})_(.+)\.sql$")


class MigrationError(RuntimeError):
    """Schema cannot be brought to a consistent state."""


def available() -> list[tuple[int, str, Path]]:
    files: list[tuple[int, str, Path]] = []
    for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
        match = FILENAME_RE.match(path.name)
        if not match:
            raise MigrationError(f"nama file migrasi tidak valid: {path.name}")
        files.append((int(match.group(1)), path.stem, path))
    if not files:
        raise MigrationError("tidak ada file migrasi ditemukan")
    return files


def _checksum(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _ensure_table(cursor) -> None:
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version    INTEGER PRIMARY KEY,
            name       TEXT NOT NULL,
            checksum   TEXT NOT NULL,
            applied_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
        )
        """
    )


def applied(cursor) -> dict[int, tuple[str, str]]:
    _ensure_table(cursor)
    cursor.execute("SELECT version, name, checksum FROM schema_migrations")
    return {row["version"]: (row["name"], row["checksum"]) for row in cursor.fetchall()}


def current_version() -> int:
    with db.connection() as cursor:
        rows = applied(cursor)
        return max(rows) if rows else 0


def apply() -> int:
    """Apply pending migrations. Returns the resulting schema version."""
    files = available()
    newest_file = files[-1][0]

    with db.connection(immediate=True) as cursor:
        done = applied(cursor)

        if done and max(done) > newest_file:
            raise MigrationError(
                f"database versi {max(done)} lebih baru dari aplikasi (maks {newest_file}); "
                "jalankan versi aplikasi yang sesuai"
            )

        by_version = {version: (name, path) for version, name, path in files}
        for version, (entry_name, checksum) in done.items():
            entry = by_version.get(version)
            if entry is None:
                raise MigrationError(f"migrasi {version} tercatat di database tetapi filenya hilang")
            if _checksum(entry[1]) != checksum:
                raise MigrationError(
                    f"checksum migrasi {version} ({entry_name}) berubah; "
                    "file migrasi yang sudah diterapkan tidak boleh diedit"
                )

        for version, name, path in files:
            if version in done:
                continue
            script = path.read_text(encoding="utf-8")
            # executescript() issues an implicit COMMIT before running, which
            # would silently drop the surrounding BEGIN IMMEDIATE and leave a
            # failed migration half-applied. Run statement by statement on the
            # existing cursor so the whole migration stays in one transaction.
            for statement in _split_statements(script):
                cursor.execute(statement)
            cursor.execute(
                "INSERT INTO schema_migrations (version, name, checksum) VALUES (?, ?, ?)",
                (version, name, _checksum(path)),
            )

    return newest_file


def _split_statements(script: str) -> list[str]:
    """Split a migration file into complete SQL statements.

    sqlite3.execute() takes one statement at a time, and manipulating
    sqlite3.complete_statement state by hand is fragile. Splitting on `;` at the
    end of a line is enough for these migrations: they contain no triggers and
    no string literal spanning a semicolon.
    """
    statements: list[str] = []
    buffer: list[str] = []
    for line in script.splitlines(keepends=True):
        buffer.append(line)
        if line.rstrip().endswith(";"):
            chunk = "".join(buffer).strip()
            if chunk:
                statements.append(chunk)
            buffer = []
    tail = "".join(buffer).strip()
    if tail:
        statements.append(tail)
    return statements
