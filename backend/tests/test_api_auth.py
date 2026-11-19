"""Login/logout/me/password against the real session code (no fakes)."""

import pytest
from fastapi.testclient import TestClient

from tuyabot.access import sessions
from tuyabot.storage.repos import roles, web_users
from tuyabot.web.app import create_app


@pytest.fixture()
def auth_client(ready_db):
    web_users.create("root", "password-panjang", roles.get_by_slug("superadmin")["id"])
    client = TestClient(create_app())
    csrf = client.get("/api/auth/csrf").json()["csrf_token"]
    return client, csrf


def login(client, csrf, username="root", password="password-panjang"):
    return client.post(
        "/api/auth/login",
        json={"username": username, "password": password},
        headers={"X-CSRF-Token": csrf},
    )


def test_login_success_sets_cookie_and_me(auth_client):
    client, csrf = auth_client
    response = login(client, csrf)
    assert response.status_code == 200
    assert "tuyabot_session" in client.cookies

    me = client.get("/api/auth/me").json()
    assert me["username"] == "root"
    assert me["role"]["slug"] == "superadmin"
    assert "manage_users" in me["permissions"]
    assert me["csrf_token"]


def test_wrong_password_is_401_and_audited(auth_client):
    from tuyabot.storage.repos import audit

    client, csrf = auth_client
    response = login(client, csrf, password="salah-sekali")
    assert response.status_code == 401
    rows = audit.list_page(action="auth.login", result="denied")
    assert rows and rows[0]["details"]["reason"] == "bad_credentials"


def test_unknown_user_gives_same_answer(auth_client):
    client, csrf = auth_client
    response = login(client, csrf, username="tidakada")
    assert response.status_code == 401
    assert response.json()["detail"] == "Username atau password salah"


def test_login_rate_limited_after_budget(auth_client):
    from tuyabot.settings import service

    service.patch({"security.login_max_attempts": 2}, actor={})
    client, csrf = auth_client
    login(client, csrf, password="salah-1")
    login(client, csrf, password="salah-2")
    response = login(client, csrf, password="salah-3")
    assert response.status_code == 429
    assert response.headers["Retry-After"]


def test_logout_revokes_session(auth_client):
    client, csrf = auth_client
    login_response = login(client, csrf)
    csrf = login_response.json()["csrf_token"]  # login rotates the CSRF binding
    token = client.cookies.get("tuyabot_session")

    assert client.post("/api/auth/logout", headers={"X-CSRF-Token": csrf}).status_code == 200
    assert sessions.resolve(token) is None
    assert client.get("/api/auth/me").status_code == 401


def test_password_change_revokes_other_sessions(auth_client):
    client, csrf = auth_client
    login_response = login(client, csrf)
    csrf = login_response.json()["csrf_token"]
    first_token = client.cookies.get("tuyabot_session")

    second = TestClient(create_app())
    second_csrf = second.get("/api/auth/csrf").json()["csrf_token"]
    second.post(
        "/api/auth/login",
        json={"username": "root", "password": "password-panjang"},
        headers={"X-CSRF-Token": second_csrf},
    )
    second_token = second.cookies.get("tuyabot_session")
    assert sessions.resolve(second_token) is not None

    response = client.post(
        "/api/auth/password",
        json={"current_password": "password-panjang", "new_password": "password-baru-panjang"},
        headers={"X-CSRF-Token": csrf},
    )
    assert response.status_code == 200
    assert response.json()["sessions_revoked"] == 1
    assert sessions.resolve(first_token) is not None
    assert sessions.resolve(second_token) is None


def test_me_requires_auth(ready_db):
    client = TestClient(create_app())
    assert client.get("/api/auth/me").status_code == 401


def test_api_key_principal_works(ready_db):
    from tuyabot.storage.repos import api_keys

    viewer = roles.get_by_slug("viewer")
    _, raw = api_keys.create("script", viewer["id"])

    client = TestClient(create_app())
    me = client.get("/api/auth/me", headers={"X-API-Key": raw}).json()
    assert me["actor_kind"] == "api_key"
    assert me["role"]["slug"] == "viewer"
    assert "monitoring" in me["permissions"]

    # A session is authorized by authentication; an API key stays scoped to the
    # permissions of its role (see tests/test_api_key_scope.py).
    assert client.get("/api/settings", headers={"X-API-Key": raw}).status_code == 403
    assert client.get("/api/auth/me", headers={"X-API-Key": "tbk_salah"}).status_code == 401
