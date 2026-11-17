"""Password hashing and session lifecycle."""

from datetime import datetime, timedelta

import pytest

from tuyabot.access import passwords, sessions
from tuyabot.storage import db


def test_password_roundtrip_and_wrong_password():
    stored = passwords.hash_password("s3cret-panjang")
    assert stored.startswith("scrypt$")
    assert passwords.verify_password("s3cret-panjang", stored)
    assert not passwords.verify_password("salah", stored)


def test_password_is_salted():
    assert passwords.hash_password("sama-sekali") != passwords.hash_password("sama-sekali")


def test_short_password_rejected():
    with pytest.raises(passwords.WeakPassword):
        passwords.hash_password("pendek")


def test_malformed_hash_does_not_raise():
    assert passwords.verify_password("apa saja", "bukan-format") is False


def _make_user(role_slug: str = "viewer") -> int:
    from tuyabot.storage.repos import roles, web_users

    return web_users.create("user1", "password-panjang", roles.get_by_slug(role_slug)["id"])


def test_session_roundtrip_and_revision(ready_db):
    user_id = _make_user()
    token = sessions.create(user_id, ttl_hours=1)

    assert sessions.resolve(token) is not None
    assert sessions.resolve(token + "salah") is None

    assert sessions.revoke(token) is True
    assert sessions.resolve(token) is None


def test_expired_session_returns_none(ready_db):
    user_id = _make_user()
    token = sessions.create(user_id, ttl_hours=1)

    past = (datetime.now() - timedelta(hours=2)).strftime("%Y-%m-%d %H:%M:%S")
    with db.connection(immediate=True) as cur:
        cur.execute(
            "UPDATE web_sessions SET expires_at = ? WHERE token_hash = ?",
            (past, sessions.token_hash(token)),
        )
    assert sessions.resolve(token) is None


def test_idle_timeout(ready_db):
    user_id = _make_user()
    token = sessions.create(user_id, ttl_hours=5)

    long_ago = (datetime.now() - timedelta(hours=3)).strftime("%Y-%m-%d %H:%M:%S")
    with db.connection(immediate=True) as cur:
        cur.execute(
            "UPDATE web_sessions SET last_seen_at = ? WHERE token_hash = ?",
            (long_ago, sessions.token_hash(token)),
        )
    assert sessions.resolve(token, idle_minutes=60) is None


def test_deactivated_user_session_is_invalid(ready_db):
    from tuyabot.storage.repos import web_users

    user_id = _make_user()
    token = sessions.create(user_id, ttl_hours=5)
    web_users.update(user_id, is_active=False)
    assert sessions.resolve(token) is None


def test_revoke_all_keeps_current_token(ready_db):
    user_id = _make_user()
    keep = sessions.create(user_id, ttl_hours=5)
    other = sessions.create(user_id, ttl_hours=5)

    assert sessions.revoke_all(user_id, except_token=keep) == 1
    assert sessions.resolve(keep) is not None
    assert sessions.resolve(other) is None


def test_sweep_removes_expired_and_revoked(ready_db):
    user_id = _make_user()
    live = sessions.create(user_id, ttl_hours=5)
    killed = sessions.create(user_id, ttl_hours=5)
    sessions.revoke(killed)

    assert sessions.sweep() == 1
    assert sessions.resolve(live) is not None


def test_only_hashes_are_stored(ready_db):
    user_id = _make_user()
    token = sessions.create(user_id, ttl_hours=5)
    with db.connection() as cur:
        cur.execute("SELECT token_hash FROM web_sessions")
        stored = cur.fetchone()[0]
    assert stored != token
    assert len(stored) == 64
