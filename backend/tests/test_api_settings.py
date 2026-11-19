"""Settings API: auth gating, atomic patch, error shape."""

from tuyabot.storage.repos import audit


def test_read_requires_settings_view(client, login_as):
    login_as("superadmin")
    response = client.get("/api/settings")
    assert response.status_code == 200
    body = response.json()
    assert body["values"]["monitoring.power_interval_minutes"] == 5
    # Token bot bukan setting: disimpan di tabel telegram_bots.
    assert "telegram.bot_token" not in body["values"]


def test_any_authenticated_account_can_read_settings(client, login_as):
    """The web has one account; authentication is the authorization."""
    login_as("superadmin")
    assert client.get("/api/settings").status_code == 200


def test_patch_writes_and_audits(client, login_as):
    login_as("superadmin")
    response = client.patch("/api/settings", json={"values": {"ui.title": "Rumah"}})
    assert response.status_code == 200
    assert response.json()["changed"]["ui.title"] == {"old": "Tuya", "new": "Rumah"}

    rows = audit.list_page(action="settings.patch")
    assert len(rows) == 1
    assert rows[0]["details"]["changed"]["ui.title"]["new"] == "Rumah"


def test_patch_returns_keyed_errors(client, login_as):
    login_as("superadmin")
    response = client.patch(
        "/api/settings",
        json={"values": {"ui.title": "X", "monitoring.power_interval_minutes": 0}},
    )
    assert response.status_code == 422
    assert response.json()["detail"]["errors"][0]["key"] == "monitoring.power_interval_minutes"
    assert client.get("/api/settings").json()["values"]["ui.title"] == "Tuya"


def test_patch_requires_values_object(client, login_as):
    login_as("superadmin")
    assert client.patch("/api/settings", json={"ui.title": "X"}).status_code == 422
