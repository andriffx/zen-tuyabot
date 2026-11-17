"""Health endpoint without any auth or database access."""

from fastapi.testclient import TestClient

from tuyabot.web.app import create_app


def test_healthz_is_public_and_does_not_touch_db():
    client = TestClient(create_app())
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
