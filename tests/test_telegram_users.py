"""Telegram users are a different entity from web accounts."""

from tuyabot.storage.repos import roles, telegram_users, web_users


def _role_id(slug: str) -> int:
    return roles.get_by_slug(slug)["id"]


def test_telegram_user_has_no_web_row(client, login_as):
    login_as("superadmin")
    response = client.post(
        "/api/telegram-users",
        json={"telegram_id": 111, "label": "Budi", "role_id": _role_id("operator")},
    )
    assert response.status_code == 200
    assert response.json()["telegram_id"] == 111

    # No web account was created, and the Telegram user cannot log in.
    assert web_users.get_by_username("budi") is None
    assert web_users.list_all() == []


def test_web_account_cannot_be_used_as_telegram_user(client, login_as, ready_db):
    from tuyabot.telegram import guards

    login_as("superadmin")
    web_users.create("webby", "password-panjang", _role_id("operator"))
    assert guards.resolve(999) is None  # no telegram_user row for this id


def test_unregistered_telegram_user_resolves_to_public(ready_db):
    from tuyabot.telegram import guards

    assert guards.resolve(424242) is None


def test_registered_telegram_user_gets_role_permissions(ready_db):
    from tuyabot.telegram import guards

    telegram_users.upsert(777, _role_id("operator"), label="Oper")
    principal = guards.resolve(777)
    assert principal is not None
    assert principal.actor_kind == "telegram"
    assert principal.role_slug == "operator"
    assert "devices.control" in principal.permissions
    assert "users.manage" not in principal.permissions


def test_inactive_telegram_user_resolves_to_public(ready_db):
    from tuyabot.telegram import guards

    telegram_users.upsert(778, _role_id("operator"))
    telegram_users.set_active(778, False)
    assert guards.resolve(778) is None


def test_api_rejects_non_integer_telegram_id(client, login_as):
    login_as("superadmin")
    response = client.post("/api/telegram-users", json={"telegram_id": "abc", "role_id": _role_id("viewer")})
    assert response.status_code == 422


def test_api_cannot_grant_higher_role(client, login_as):
    login_as("admin")
    response = client.post(
        "/api/telegram-users", json={"telegram_id": 555, "role_id": _role_id("superadmin")}
    )
    assert response.status_code == 403


def test_role_change_and_delete_are_audited(client, login_as):
    from tuyabot.storage.repos import audit

    login_as("superadmin")
    client.post("/api/telegram-users", json={"telegram_id": 888, "role_id": _role_id("viewer")})
    client.patch("/api/telegram-users/888", json={"role_id": _role_id("operator")})
    client.delete("/api/telegram-users/888")

    actions = [row["action"] for row in audit.list_page(target_kind="telegram_user")]
    assert actions[:3] == ["telegram_users.delete", "telegram_users.update", "telegram_users.create"]
