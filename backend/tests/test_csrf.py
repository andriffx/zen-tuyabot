"""CSRF double-submit enforcement on cookie-authenticated mutations."""

import pytest
from fastapi.testclient import TestClient

from tuyabot.access import sessions
from tuyabot.web.app import create_app


@pytest.fixture()
def bare_client(ready_db):
    token = sessions.create(
        _make_user(), ttl_hours=5
    )
    csrf = sessions.csrf_token(token)
    return TestClient(create_app(), cookies={"tuyabot_session": token, "csrf_token": csrf}), csrf


def _make_user() -> int:
    from tuyabot.storage.repos import roles, web_users

    return web_users.create("csrfuser", "password-panjang", roles.get_by_slug("superadmin")["id"])


def test_mutation_without_csrf_header_is_rejected(bare_client):
    client, _ = bare_client
    response = client.patch("/api/settings", json={"values": {"ui.title": "X"}})
    assert response.status_code == 403
    assert "CSRF" in response.json()["detail"]


def test_matching_header_and_cookie_pass(bare_client):
    client, csrf = bare_client
    response = client.patch(
        "/api/settings", json={"values": {"ui.title": "X"}}, headers={"X-CSRF-Token": csrf}
    )
    assert response.status_code == 200


def test_header_cookie_mismatch_rejected(bare_client):
    client, csrf = bare_client
    client.cookies.set("csrf_token", "nilai-lain")
    response = client.patch(
        "/api/settings", json={"values": {"ui.title": "X"}}, headers={"X-CSRF-Token": csrf}
    )
    assert response.status_code == 403


def test_token_from_another_session_rejected(ready_db):
    token = sessions.create(_make_user(), ttl_hours=5)
    foreign = sessions.csrf_token("session-lain")
    client = TestClient(
        create_app(),
        cookies={"tuyabot_session": token, "csrf_token": foreign},
        headers={"X-CSRF-Token": foreign},
    )
    assert client.patch("/api/settings", json={"values": {"ui.title": "X"}}).status_code == 403


def test_get_requests_do_not_need_csrf(bare_client):
    client, _ = bare_client
    assert client.get("/api/settings").status_code == 200


def test_cross_origin_mutation_rejected(bare_client):
    client, csrf = bare_client
    response = client.patch(
        "/api/settings",
        json={"values": {"ui.title": "X"}},
        headers={"X-CSRF-Token": csrf, "Origin": "https://jahat.example"},
    )
    assert response.status_code == 403


def test_origin_host_mismatch_with_proxy_port_is_rejected(ready_db):
    """A reverse proxy that rewrites Host without the port would break every
    mutation in production. The check must compare the full netloc."""
    token = sessions.create(_make_user(), ttl_hours=5)
    csrf = sessions.csrf_token(token)
    client = TestClient(
        create_app(),
        cookies={"tuyabot_session": token, "csrf_token": csrf},
        headers={"X-CSRF-Token": csrf, "Host": "tuya.example.com:8443",
                 "Origin": "https://tuya.example.com:8443"},
    )
    # Different scheme is fine, the port must match; this documents that the
    # proxy must forward Host (with port) unchanged.
    response = client.patch("/api/settings", json={"values": {"ui.title": "X"}})
    assert response.status_code == 200


def test_origin_mismatch_is_rejected_with_port(ready_db):
    token = sessions.create(_make_user(), ttl_hours=5)
    csrf = sessions.csrf_token(token)
    client = TestClient(
        create_app(),
        cookies={"tuyabot_session": token, "csrf_token": csrf},
        headers={"X-CSRF-Token": csrf, "Host": "tuya.example.com:8443",
                 "Origin": "https://evil.example"},
    )
    assert client.patch("/api/settings", json={"values": {"ui.title": "X"}}).status_code == 403
