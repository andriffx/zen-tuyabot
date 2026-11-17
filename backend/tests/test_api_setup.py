"""First-run gating and the setup endpoint."""

import pytest
from fastapi.testclient import TestClient

from tuyabot.storage import db, migrate
from tuyabot.storage.repos import app_state, audit, roles, web_users
from tuyabot.web.app import create_app


@pytest.fixture()
def fresh_client(fresh_db):
    """A migrated but NOT set-up instance."""
    from tuyabot import bootstrap

    migrate.apply()
    bootstrap._secret = b"test-secret-32-bytes-long-padding!"
    app_state.reset_cache()
    client = TestClient(create_app())
    csrf = client.get("/api/auth/csrf").json()["csrf_token"]
    return client, csrf


def setup(client, csrf, username="root", password="password-panjang"):
    return client.post(
        "/api/setup",
        json={"username": username, "password": password},
        headers={"X-CSRF-Token": csrf},
    )


def test_command_exists():
    assert roles is not None and web_users is not None and db is not None


def test_fresh_instance_reports_setup_required(fresh_client):
    client, _ = fresh_client
    assert client.get("/api/setup/status").json()["required"] is True


def test_everything_is_gated_before_setup(fresh_client):
    client, _ = fresh_client
    response = client.get("/api/settings")
    assert response.status_code == 409
    assert response.json()["setup_required"] is True
    assert client.get("/healthz").status_code == 200
    assert client.get("/api/auth/csrf").status_code == 200


def test_setup_creates_superadmin_and_logs_in(fresh_client):
    client, csrf = fresh_client
    response = setup(client, csrf)
    assert response.status_code == 200
    assert response.json()["csrf_token"]

    me = client.get("/api/auth/me").json()
    assert me["username"] == "root"
    assert me["role"]["slug"] == "superadmin"
    assert "system.restore" in me["permissions"]


def test_setup_runs_only_once(fresh_client):
    client, csrf = fresh_client
    first = setup(client, csrf)
    assert first.status_code == 200
    # Setup issues a session; later mutations need the session-bound CSRF token.
    csrf = first.json()["csrf_token"]
    second = setup(client, csrf, username="lain")
    assert second.status_code == 409
    assert web_users.list_all()[0]["username"] == "root"


def test_setup_creates_no_telegram_user(fresh_client):
    client, csrf = fresh_client
    setup(client, csrf)
    with db.connection() as cur:
        cur.execute("SELECT COUNT(*) FROM telegram_users")
        assert cur.fetchone()[0] == 0


def test_setup_rejects_weak_password(fresh_client):
    client, csrf = fresh_client
    response = setup(client, csrf, password="123")
    assert response.status_code == 422


def test_setup_is_audited(fresh_client):
    client, csrf = fresh_client
    setup(client, csrf)
    rows = audit.list_page(action="setup.complete")
    assert len(rows) == 1
    assert rows[0]["result"] == "ok"


def test_denied_mutation_is_audited(fresh_client):
    client, csrf = fresh_client
    setup(client, csrf)

    viewer = roles.get_by_slug("viewer")
    web_users.create("tamuku", "password-panjang", viewer["id"])

    viewer_client = TestClient(create_app())
    viewer_csrf = viewer_client.get("/api/auth/csrf").json()["csrf_token"]
    login = viewer_client.post(
        "/api/auth/login",
        json={"username": "tamuku", "password": "password-panjang"},
        headers={"X-CSRF-Token": viewer_csrf},
    )
    assert login.status_code == 200
    viewer_csrf = login.json()["csrf_token"]

    response = viewer_client.post(
        "/api/web-users",
        json={"username": "x", "password": "password-panjang", "role_id": viewer["id"]},
        headers={"X-CSRF-Token": viewer_csrf},
    )
    assert response.status_code == 403

    denied = audit.list_page(action="access.denied", result="denied")
    assert len(denied) == 1
    assert denied[0]["actor_label"] == "tamuku"
    assert denied[0]["details"]["path"] == "/api/web-users"
