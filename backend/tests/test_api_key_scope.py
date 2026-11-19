"""API keys stay role-scoped.

The web dashboard has one account, so a *session* is authorized by being
authenticated. An API key is different: it is an automation credential bound to
a role, and relaxing require() must not hand every key the owner's powers.
"""

from fastapi.testclient import TestClient

from tuyabot.storage.repos import api_keys, roles
from tuyabot.web.app import create_app


def test_a_viewer_key_cannot_reach_settings(ready_db):
    _, raw = api_keys.create("script", roles.get_by_slug("viewer")["id"])
    client = TestClient(create_app())

    response = client.get("/api/settings", headers={"X-API-Key": raw})

    assert response.status_code == 403


def test_a_viewer_key_cannot_reach_bots_or_backup(ready_db):
    _, raw = api_keys.create("script", roles.get_by_slug("viewer")["id"])
    client = TestClient(create_app())
    headers = {"X-API-Key": raw}

    assert client.get("/api/bots", headers=headers).status_code == 403
    assert client.get("/api/backup", headers=headers).status_code == 403


def test_a_viewer_key_still_reaches_its_own_scope(ready_db):
    """A key must keep working for what its role was granted."""
    _, raw = api_keys.create("script", roles.get_by_slug("viewer")["id"])
    client = TestClient(create_app())

    assert client.get("/api/devices", headers={"X-API-Key": raw}).status_code == 200
