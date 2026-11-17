"""Web user and role management: escalation guards and last-admin protection."""

from tuyabot.storage.repos import roles, web_users


def _role_id(slug: str) -> int:
    return roles.get_by_slug(slug)["id"]


def test_cannot_grant_role_with_permissions_not_held(client, login_as):
    login_as("admin")  # admin lacks users.manage
    response = client.post(
        "/api/web-users",
        json={"username": "x", "password": "password-panjang", "role_id": _role_id("viewer")},
    )
    assert response.status_code == 403


def test_superadmin_creates_user(client, login_as):
    login_as("superadmin")
    response = client.post(
        "/api/web-users",
        json={"username": "operator1", "password": "password-panjang", "role_id": _role_id("operator")},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["username"] == "operator1"
    assert "password_hash" not in body


def test_duplicate_username_returns_422(client, login_as):
    login_as("superadmin")
    payload = {"username": "dup", "password": "password-panjang", "role_id": _role_id("viewer")}
    assert client.post("/api/web-users", json=payload).status_code == 200
    duplicate = client.post("/api/web-users", json=payload)
    assert duplicate.status_code == 422
    assert duplicate.json()["detail"]["errors"][0]["key"] == "username"


def test_weak_password_rejected(client, login_as):
    login_as("superadmin")
    response = client.post(
        "/api/web-users",
        json={"username": "lemah", "password": "123", "role_id": _role_id("viewer")},
    )
    assert response.status_code == 422


def test_cannot_edit_account_with_higher_permissions(client, login_as):
    LoginAs = login_as
    LoginAs("admin")
    superadmin_role = roles.get_by_slug("superadmin")["id"]
    target_id = web_users.create("boss", "password-panjang", superadmin_role)
    response = client.patch(f"/api/web-users/{target_id}", json={"is_active": False})
    assert response.status_code == 403


def test_last_manager_cannot_be_deactivated(client, login_as):
    login_as("superadmin")
    me_id = web_users.create("root", "password-panjang", _role_id("superadmin"))
    users = web_users.list_all()
    assert len(users) == 1
    response = client.patch(f"/api/web-users/{users[0]['id']}", json={"is_active": False})
    assert response.status_code == 409
    assert web_users.get(me_id)["is_active"] == 1


def test_role_change_revokes_sessions(client, login_as):
    from tuyabot.access import sessions

    login_as("superadmin")
    user_id = web_users.create("diubah", "password-panjang", _role_id("operator"))
    token = sessions.create(user_id, ttl_hours=5)

    response = client.patch(f"/api/web-users/{user_id}", json={"role_id": _role_id("viewer")})
    assert response.status_code == 200
    assert sessions.resolve(token) is None


def test_role_creation_rejects_unknown_permission(client, login_as):
    login_as("superadmin")
    response = client.post("/api/roles", json={"slug": "tamu", "name": "Tamu", "permissions": ["tidak.ada"]})
    assert response.status_code == 422


def test_role_creation_cannot_grant_more_than_holder(client, login_as):
    login_as("admin")
    response = client.post(
        "/api/roles", json={"slug": "calo", "name": "Calo", "permissions": ["devices.view", "system.restore"]}
    )
    assert response.status_code == 403


def test_protected_role_cannot_lose_required_permission(client, login_as):
    login_as("superadmin")
    superadmin = roles.get_by_slug("superadmin")
    remaining = [key for key in superadmin["permissions"] if key != "roles.manage"]
    response = client.patch(f"/api/roles/{superadmin['id']}", json={"permissions": remaining})
    assert response.status_code == 409


def test_protected_role_cannot_be_deleted(client, login_as):
    login_as("superadmin")
    superadmin = roles.get_by_slug("superadmin")
    assert client.delete(f"/api/roles/{superadmin['id']}").status_code == 409


def test_role_in_use_cannot_be_deleted(client, login_as):
    login_as("superadmin")
    operator = roles.get_by_slug("operator")
    web_users.create("pakai", "password-panjang", operator["id"])
    response = client.delete(f"/api/roles/{operator['id']}")
    assert response.status_code == 409
    assert response.json()["detail"]["references"]["web_users"] == 1


def test_permission_catalog_is_grouped(client, login_as):
    login_as("superadmin")
    body = client.get("/api/roles/permissions").json()
    assert len(body["all"]) == 23
    assert any(group["name"] == "Device" for group in body["categories"])


def test_editing_the_actors_own_role_revokes_their_session(client, login_as):
    """Saving role permissions revokes every session using that role, including
    the editor's own — otherwise a removed permission would stay live until the
    cookie expired. The UI must therefore handle a 401 on its next request."""
    from tuyabot.access import sessions
    from tuyabot.storage.repos import roles

    login_as("superadmin")
    role = roles.get_by_slug("superadmin")
    user_id = web_users.create("self", "password-panjang", role["id"])
    token = sessions.create(user_id, ttl_hours=1)

    response = client.patch(f"/api/roles/{role['id']}", json={"permissions": role["permissions"]})
    assert response.status_code == 200
    assert set(response.json()["permissions"]) == set(role["permissions"])

    assert sessions.resolve(token) is None
