"""backup_runs repository."""

from __future__ import annotations

from typing import Any

from .. import db


def record(filename: str, size_bytes: int, kind: str, note: str | None = None) -> int:
    with db.connection(immediate=True) as cur:
        cur.execute(
            "INSERT INTO backup_runs (filename, size_bytes, kind, note) VALUES (?, ?, ?, ?)",
            (filename, int(size_bytes), kind, note),
        )
        return int(cur.lastrowid)


def list_all(limit: int = 100) -> list[dict[str, Any]]:
    with db.connection() as cur:
        cur.execute(
            "SELECT * FROM backup_runs ORDER BY created_at DESC, id DESC LIMIT ?",
            (max(1, min(limit, 200)),),
        )
        return [dict(row) for row in cur.fetchall()]


def get(run_id: int) -> dict[str, Any] | None:
    with db.connection() as cur:
        cur.execute("SELECT * FROM backup_runs WHERE id = ?", (run_id,))
        row = cur.fetchone()
        return dict(row) if row else None


def forget(filename: str) -> None:
    with db.connection(immediate=True) as cur:
        cur.execute("DELETE FROM backup_runs WHERE filename = ?", (filename,))


def last() -> dict[str, Any] | None:
    with db.connection() as cur:
        cur.execute("SELECT * FROM backup_runs ORDER BY created_at DESC, id DESC LIMIT 1")
        row = cur.fetchone()
        return dict(row) if row else None
