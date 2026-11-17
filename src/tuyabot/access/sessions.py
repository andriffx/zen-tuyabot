"""Sessions: opaque tokens, hashed at rest, bound to the app secret.

The DB stores only sha256(secret.key + token), so a leaked database file does
not hand over live sessions.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta

from .. import bootstrap
from ..storage import db

TOKEN_BYTES = 32
TOUCH_INTERVAL_SECONDS = 60


def _now() -> datetime:
    return datetime.now()


def _fmt(value: datetime) -> str:
    return value.strftime("%Y-%m-%d %H:%M:%S")


def _parse(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%d %H:%M:%S")


def token_hash(token: str) -> str:
    key = bootstrap.secret() or b"insecure-development-key"
    return hashlib.sha256(key + token.encode()).hexdigest()


def create(
    user_id: int,
    *,
    ttl_hours: int = 12,
    ip: str | None = None,
    user_agent: str | None = None,
) -> str:
    token = secrets.token_urlsafe(TOKEN_BYTES)
    expires = _now() + timedelta(hours=ttl_hours)
    with db.connection(immediate=True) as cur:
        cur.execute(
            """
            INSERT INTO web_sessions (token_hash, user_id, expires_at, ip, user_agent)
            VALUES (?, ?, ?, ?, ?)
            """,
            (token_hash(token), user_id, _fmt(expires), ip, (user_agent or "")[:255]),
        )
    return token


def resolve(token: str, *, idle_minutes: int = 60) -> dict | None:
    """Return the session row joined with the user, or None if invalid.

    Invalid means: unknown token, revoked, expired, or idle beyond the limit.
    """
    if not token:
        return None
    with db.connection() as cur:
        cur.execute(
            """
            SELECT s.*, u.username, u.role_id, u.is_active
            FROM web_sessions s
            JOIN web_users u ON u.id = s.user_id
            WHERE s.token_hash = ?
            """,
            (token_hash(token),),
        )
        row = cur.fetchone()
        if row is None:
            return None

        session = dict(row)
        if session.get("revoked_at"):
            return None
        if not session.get("is_active"):
            return None

        now = _now()
        if _parse(session["expires_at"]) <= now:
            return None
        last_seen = _parse(session["last_seen_at"])
        if now - last_seen > timedelta(minutes=idle_minutes):
            return None

        if (now - last_seen).total_seconds() >= TOUCH_INTERVAL_SECONDS:
            cur.execute(
                "UPDATE web_sessions SET last_seen_at = datetime('now','localtime') WHERE token_hash = ?",
                (session["token_hash"],),
            )
    return session


def revoke(token: str) -> bool:
    with db.connection(immediate=True) as cur:
        cur.execute(
            "UPDATE web_sessions SET revoked_at = datetime('now','localtime') "
            "WHERE token_hash = ? AND revoked_at IS NULL",
            (token_hash(token),),
        )
        return cur.rowcount > 0


def revoke_all(user_id: int, *, except_token: str | None = None) -> int:
    with db.connection(immediate=True) as cur:
        if except_token:
            cur.execute(
                "UPDATE web_sessions SET revoked_at = datetime('now','localtime') "
                "WHERE user_id = ? AND token_hash <> ? AND revoked_at IS NULL",
                (user_id, token_hash(except_token)),
            )
        else:
            cur.execute(
                "UPDATE web_sessions SET revoked_at = datetime('now','localtime') "
                "WHERE user_id = ? AND revoked_at IS NULL",
                (user_id,),
            )
        return cur.rowcount


def revoke_for_role(role_id: int) -> int:
    with db.connection(immediate=True) as cur:
        cur.execute(
            """
            UPDATE web_sessions SET revoked_at = datetime('now','localtime')
            WHERE revoked_at IS NULL AND user_id IN (
                SELECT id FROM web_users WHERE role_id = ?
            )
            """,
            (role_id,),
        )
        return cur.rowcount


def revoke_for_user(user_id: int) -> int:
    return revoke_all(user_id)


def list_for(user_id: int) -> list[dict]:
    with db.connection() as cur:
        cur.execute(
            """
            SELECT token_hash, user_id, created_at, expires_at, last_seen_at, ip, user_agent, revoked_at
            FROM web_sessions WHERE user_id = ? ORDER BY created_at DESC LIMIT 100
            """,
            (user_id,),
        )
        return [dict(row) for row in cur.fetchall()]


def sweep() -> int:
    with db.connection(immediate=True) as cur:
        cur.execute(
            "DELETE FROM web_sessions WHERE expires_at < datetime('now','localtime') "
            "OR revoked_at IS NOT NULL"
        )
        return cur.rowcount


def csrf_token(token: str) -> str:
    """Bind the CSRF token to the session so it cannot be reused across sessions."""
    mac = hmac.new(bootstrap.secret() or b"insecure-development-key", token_hash(token).encode(), hashlib.sha256)
    return base64.urlsafe_b64encode(mac.digest()).decode().rstrip("=")


def verify_csrf(token: str, header_value: str, cookie_value: str) -> bool:
    if not header_value or not cookie_value:
        return False
    expected = csrf_token(token)
    return hmac.compare_digest(header_value, cookie_value) and hmac.compare_digest(header_value, expected)
