"""Telegram user registry — a separate entity from web accounts.

A Telegram user is identified only by `telegram_id`; they have no password and
can never log into the dashboard. Sharing `roles` is all the two kinds of
identity have in common.
"""

from __future__ import annotations

from typing import Any

from .. import db


class TelegramUserError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def list_all() -> list[dict[str, Any]]:
    with db.connection() as cur:
        cur.execute(
            """
            SELECT t.*, r.slug AS role_slug, r.name AS role_name
            FROM telegram_users t
            JOIN roles r ON r.id = t.role_id
            ORDER BY t.telegram_id
            """
        )
        return [dict(row) for row in cur.fetchall()]


def get(telegram_id: int) -> dict[str, Any] | None:
    with db.connection() as cur:
        cur.execute(
            """
            SELECT t.*, r.slug AS role_slug, r.name AS role_name, r.permissions AS role_permissions
            FROM telegram_users t
            JOIN roles r ON r.id = t.role_id
            WHERE t.telegram_id = ?
            """,
            (telegram_id,),
        )
        row = cur.fetchone()
        return dict(row) if row else None


def upsert(
    telegram_id: int,
    role_id: int,
    *,
    label: str | None = None,
    created_by_web_user_id: int | None = None,
    created_by_telegram_id: int | None = None,
) -> None:
    if isinstance(telegram_id, bool) or not isinstance(telegram_id, int) or telegram_id <= 0:
        raise TelegramUserError("telegram_id", "telegram_id harus angka positif")
    with db.connection(immediate=True) as cur:
        cur.execute(
            """
            INSERT INTO telegram_users
                (telegram_id, label, role_id, created_by_web_user_id, created_by_telegram_id)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(telegram_id) DO UPDATE SET
                label = COALESCE(excluded.label, telegram_users.label),
                role_id = excluded.role_id,
                updated_at = datetime('now','localtime')
            """,
            (telegram_id, label, role_id, created_by_web_user_id, created_by_telegram_id),
        )


def set_active(telegram_id: int, is_active: bool) -> None:
    with db.connection(immediate=True) as cur:
        cur.execute(
            "UPDATE telegram_users SET is_active = ?, updated_at = datetime('now','localtime') "
            "WHERE telegram_id = ?",
            (1 if is_active else 0, telegram_id),
        )


def delete(telegram_id: int) -> None:
    with db.connection(immediate=True) as cur:
        cur.execute("DELETE FROM telegram_users WHERE telegram_id = ?", (telegram_id,))


def touch(telegram_id: int) -> None:
    with db.connection(immediate=True) as cur:
        cur.execute(
            "UPDATE telegram_users SET last_seen_at = datetime('now','localtime') WHERE telegram_id = ?",
            (telegram_id,),
        )


def count_by_role(role_id: int) -> int:
    with db.connection() as cur:
        cur.execute("SELECT COUNT(*) FROM telegram_users WHERE role_id = ?", (role_id,))
        return int(cur.fetchone()[0])
