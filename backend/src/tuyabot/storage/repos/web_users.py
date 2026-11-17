"""Web user repository: accounts with password hashes and a single role."""

from __future__ import annotations

from typing import Any

from ...access import passwords
from .. import db


class UserError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


PUBLIC_COLUMNS = (
    "id, username, role_id, is_active, created_by, created_at, updated_at, last_login_at"
)


def list_all() -> list[dict[str, Any]]:
    with db.connection() as cur:
        cur.execute(f"SELECT {PUBLIC_COLUMNS} FROM web_users ORDER BY id")
        return [dict(row) for row in cur.fetchall()]


def get(user_id: int) -> dict[str, Any] | None:
    with db.connection() as cur:
        cur.execute(f"SELECT {PUBLIC_COLUMNS} FROM web_users WHERE id = ?", (user_id,))
        row = cur.fetchone()
        return dict(row) if row else None


def get_with_hash(user_id: int) -> dict[str, Any] | None:
    with db.connection() as cur:
        cur.execute("SELECT * FROM web_users WHERE id = ?", (user_id,))
        row = cur.fetchone()
        return dict(row) if row else None


def get_by_username(username: str) -> dict[str, Any] | None:
    with db.connection() as cur:
        cur.execute("SELECT * FROM web_users WHERE username = ?", (username,))
        row = cur.fetchone()
        return dict(row) if row else None


def count_active_managers() -> int:
    """How many active accounts hold users.manage through their role."""
    with db.connection() as cur:
        cur.execute(
            """
            SELECT COUNT(*) FROM web_users u
            JOIN roles r ON r.id = u.role_id
            WHERE u.is_active = 1
              AND EXISTS (SELECT 1 FROM json_each(r.permissions) WHERE json_each.value = 'users.manage')
            """
        )
        return int(cur.fetchone()[0])


def create(
    username: str,
    password: str,
    role_id: int,
    *,
    created_by: int | None = None,
) -> int:
    username = (username or "").strip()
    if not username:
        raise UserError("username", "Username wajib diisi")
    if len(username) > 64:
        raise UserError("username", "Username maksimal 64 karakter")
    try:
        password_hash = passwords.hash_password(password)
    except passwords.WeakPassword as exc:
        raise UserError("password", str(exc)) from exc

    try:
        with db.connection(immediate=True) as cur:
            cur.execute(
                "INSERT INTO web_users (username, password_hash, role_id, created_by) VALUES (?, ?, ?, ?)",
                (username, password_hash, role_id, created_by),
            )
            return int(cur.lastrowid)
    except Exception as exc:  # sqlite3.IntegrityError
        if "UNIQUE" in str(exc):
            raise UserError("username", "Username sudah dipakai") from exc
        raise


def update(
    user_id: int,
    *,
    password: str | None = None,
    role_id: int | None = None,
    is_active: bool | None = None,
) -> None:
    fields: dict[str, Any] = {}
    if password is not None:
        try:
            fields["password_hash"] = passwords.hash_password(password)
        except passwords.WeakPassword as exc:
            raise UserError("password", str(exc)) from exc
    if role_id is not None:
        fields["role_id"] = role_id
    if is_active is not None:
        fields["is_active"] = 1 if is_active else 0
    if not fields:
        return

    assignments = ", ".join(f"{key} = ?" for key in fields)
    values = [*fields.values(), user_id]
    with db.connection(immediate=True) as cur:
        cur.execute(
            f"UPDATE web_users SET {assignments}, updated_at = datetime('now','localtime') WHERE id = ?",
            values,
        )


def delete(user_id: int) -> None:
    with db.connection(immediate=True) as cur:
        cur.execute("DELETE FROM web_users WHERE id = ?", (user_id,))


def touch_login(user_id: int) -> None:
    with db.connection(immediate=True) as cur:
        cur.execute(
            "UPDATE web_users SET last_login_at = datetime('now','localtime') WHERE id = ?",
            (user_id,),
        )


def set_password(user_id: int, new_password: str) -> None:
    update(user_id, password=new_password)
