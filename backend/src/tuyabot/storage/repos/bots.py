"""Telegram bot repository. Tokens are write-only from the API's point of view."""

from __future__ import annotations

import hashlib
from typing import Any

from .. import db


class BotError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def token_fingerprint(token: str) -> str:
    return hashlib.sha256(token.strip().encode()).hexdigest()


def list_all() -> list[dict[str, Any]]:
    with db.connection() as cur:
        cur.execute(
            """
            SELECT id, label, enabled, bot_username, last_ok_at, last_error,
                   created_by, created_at, updated_at
            FROM telegram_bots ORDER BY id
            """
        )
        return [_public(row) for row in cur.fetchall()]


def _public(row) -> dict[str, Any]:
    record = dict(row)
    record["enabled"] = bool(record.get("enabled"))
    return record


def get(bot_id: int) -> dict[str, Any] | None:
    with db.connection() as cur:
        cur.execute("SELECT * FROM telegram_bots WHERE id = ?", (bot_id,))
        row = cur.fetchone()
        return dict(row) if row else None


def get_token(bot_id: int) -> str | None:
    record = get(bot_id)
    return record["token"] if record else None


def enabled_bots() -> list[dict[str, Any]]:
    with db.connection() as cur:
        cur.execute(
            "SELECT id, label, token, bot_username FROM telegram_bots WHERE enabled = 1 ORDER BY id"
        )
        return [dict(row) for row in cur.fetchall()]


def create(label: str, token: str, *, created_by: int | None = None) -> int:
    token = token.strip()
    if not token:
        raise BotError("token", "Token wajib diisi")
    try:
        with db.connection(immediate=True) as cur:
            cur.execute(
                "INSERT INTO telegram_bots (label, token, token_sha256, created_by) VALUES (?, ?, ?, ?)",
                (label.strip() or "Bot", token, token_fingerprint(token), created_by),
            )
            return int(cur.lastrowid)
    except Exception as exc:
        if "token_sha256" in str(exc):
            raise BotError("token", "Token ini sudah terdaftar di bot lain") from exc
        raise


def update(
    bot_id: int,
    *,
    label: str | None = None,
    token: str | None = None,
    enabled: bool | None = None,
    bot_username: str | None = None,
) -> None:
    fields: dict[str, Any] = {}
    if label is not None:
        fields["label"] = label
    if token is not None:
        fields["token"] = token.strip()
        fields["token_sha256"] = token_fingerprint(token)
    if enabled is not None:
        fields["enabled"] = 1 if enabled else 0
    if bot_username is not None:
        fields["bot_username"] = bot_username
    if not fields:
        return

    assignments = ", ".join(f"{column} = ?" for column in fields)
    values = [*fields.values(), bot_id]
    try:
        with db.connection(immediate=True) as cur:
            cur.execute(
                f"UPDATE telegram_bots SET {assignments}, updated_at = datetime('now','localtime') WHERE id = ?",
                values,
            )
    except Exception as exc:
        if "token_sha256" in str(exc):
            raise BotError("token", "Token ini sudah terdaftar di bot lain") from exc
        raise


def record_ok(bot_id: int, username: str | None) -> None:
    with db.connection(immediate=True) as cur:
        cur.execute(
            """
            UPDATE telegram_bots
            SET last_ok_at = datetime('now','localtime'), last_error = NULL,
                bot_username = COALESCE(?, bot_username),
                updated_at = datetime('now','localtime')
            WHERE id = ?
            """,
            (username, bot_id),
        )


def record_error(bot_id: int, message: str) -> None:
    """Store a start-up error. The token is redacted here as well as in the
    manager: `last_error` is served by GET /api/bots, so this repository is the
    last line of defence against leaking the one secret the API never returns."""
    record = get(bot_id)
    token = record["token"] if record else None
    cleaned = message
    if token:
        cleaned = cleaned.replace(token, "[token]")
        bare = token.split(":", 1)[0]
        if len(bare) >= 6:
            cleaned = cleaned.replace(bare, "[token]")
    with db.connection(immediate=True) as cur:
        cur.execute(
            "UPDATE telegram_bots SET last_error = ?, updated_at = datetime('now','localtime') WHERE id = ?",
            (cleaned[:500], bot_id),
        )


def delete(bot_id: int) -> None:
    with db.connection(immediate=True) as cur:
        cur.execute("DELETE FROM telegram_bots WHERE id = ?", (bot_id,))
