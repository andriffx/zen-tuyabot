"""API keys for scripts: the raw key is shown once, only its hash is stored."""

from __future__ import annotations

import hashlib
import secrets
from typing import Any

from .. import db

PREFIX = "tbk_"


def hash_key(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def list_all() -> list[dict[str, Any]]:
    with db.connection() as cur:
        cur.execute(
            "SELECT id, name, role_id, is_active, created_by, last_used_at, created_at FROM api_keys ORDER BY id"
        )
        return [dict(row) for row in cur.fetchall()]


def create(name: str, role_id: int, *, created_by: int | None = None) -> tuple[int, str]:
    """Return (id, raw_key). The raw key is never stored or returned again."""
    raw = PREFIX + secrets.token_urlsafe(32)
    with db.connection(immediate=True) as cur:
        cur.execute(
            "INSERT INTO api_keys (name, key_hash, role_id, created_by) VALUES (?, ?, ?, ?)",
            (name, hash_key(raw), role_id, created_by),
        )
        return int(cur.lastrowid), raw


def resolve(raw: str) -> dict[str, Any] | None:
    if not raw:
        return None
    with db.connection(immediate=True) as cur:
        cur.execute(
            "SELECT id, name, role_id, is_active FROM api_keys WHERE key_hash = ?",
            (hash_key(raw),),
        )
        row = cur.fetchone()
        if row is None or not row["is_active"]:
            return None
        cur.execute(
            "UPDATE api_keys SET last_used_at = datetime('now','localtime') WHERE id = ?",
            (row["id"],),
        )
        return dict(row)


def delete(key_id: int) -> None:
    with db.connection(immediate=True) as cur:
        cur.execute("DELETE FROM api_keys WHERE id = ?", (key_id,))


def revoke_for_role(role_id: int) -> int:
    with db.connection(immediate=True) as cur:
        cur.execute("UPDATE api_keys SET is_active = 0 WHERE role_id = ?", (role_id,))
        return cur.rowcount
