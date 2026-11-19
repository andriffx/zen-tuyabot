"""Role/user integrity: a role in use cannot vanish, an unknown role is refused,
and a dangling role grants nothing."""

from tuyabot.access import bot_auth
from tuyabot.storage import db
from tuyabot.storage.repos import roles, telegram_users


def test_deleting_a_role_in_use_is_refused(client, csrf_value, login_as, ready_db):
    login_as("superadmin")
    role_id = roles.create("uji", "Uji", None, [])
    telegram_users.upsert(7001, role_id, label="Budi")

    response = client.delete(
        f"/api/roles/{role_id}", headers={"X-CSRF-Token": csrf_value}
    )

    assert response.status_code == 409
    assert roles.get(role_id) is not None


def test_creating_a_telegram_user_with_an_unknown_role_is_refused(
    client, csrf_value, login_as, ready_db
):
    login_as("superadmin")

    response = client.post(
        "/api/telegram-users",
        json={"telegram_id": 7002, "role_id": 999999},
        headers={"X-CSRF-Token": csrf_value},
    )

    assert response.status_code == 422
    assert telegram_users.get(7002) is None


def test_deleting_a_role_cannot_leave_a_dangling_user(ready_db):
    """The database refuses, and the API refuses first with a 409.

    If the foreign key were ever removed, bot_auth still denies an unknown
    role_id — checks keyed on a role that does not exist return False by
    construction (see tests/test_bot_auth.py::test_unknown_role_has_nothing).
    """
    import sqlite3

    import pytest

    role_id = roles.create("sementara", "Sementara", None, [])
    telegram_users.upsert(7003, role_id, label="Budi")

    with pytest.raises(sqlite3.IntegrityError), db.connection(immediate=True) as cur:
        cur.execute("DELETE FROM roles WHERE id = ?", (role_id,))

    assert telegram_users.get(7003) is not None
    assert bot_auth.can_device(role_id, 1, "on") is False
