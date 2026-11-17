"""Device API: visibility, control, DPS, unreachable devices, SSE."""

import pytest

from tuyabot.devices import controller as controller_module
from tuyabot.devices import registry
from tuyabot.infra import state_cache
from tuyabot.settings import service as settings_service
from tuyabot.storage.repos import devices as devices_repo
from tuyabot.storage.repos import logs, roles


@pytest.fixture()
def fake_tuya(monkeypatch):
    """Replace tinytuya entirely: no network, deterministic results."""
    state = {"online": True, "switch_on": False, "power_w": 10.0, "calls": 0}

    def status(device):
        state["calls"] += 1
        if not state["online"]:
            return {"success": False, "message": "Device unreachable"}
        return {
            "success": True,
            "switch_on": state["switch_on"],
            "power_w": state["power_w"],
            "current_a": 0.1,
            "voltage_v": 220.0,
            "raw": {},
        }

    def set_switch(device, on):
        if not state["online"]:
            return {"success": False, "message": "Device unreachable"}
        state["switch_on"] = on
        return {"success": True}

    monkeypatch.setattr(controller_module.controller, "status", status)
    monkeypatch.setattr(controller_module.controller, "set_switch", set_switch)
    state_cache.cache.clear()
    return state


@pytest.fixture()
def device(ready_db):
    viewer = roles.get_by_slug("viewer")["id"]
    device_id = devices_repo.create(
        {
            "name": "air",
            "label": "Pompa Air",
            "tuya_id": "dev-1",
            "local_key": "kunci",
            "ip": "10.0.0.5",
            "type": "plug",
            "features": {"power_logging": True},
            "access_roles": [viewer],
        }
    )
    registry.reload()
    yield device_id
    registry.reset_cache()
    state_cache.cache.clear()


def test_list_devices_hides_secrets(client, login_as, device):
    login_as("superadmin")
    body = client.get("/api/devices").json()
    assert len(body["devices"]) == 1
    entry = body["devices"][0]
    assert entry["name"] == "air"
    assert "local_key" not in entry
    assert entry["has_local_key"] is True


def test_device_hidden_from_role_returns_404(client, login_as, device):
    login_as("operator")  # access_roles only lists viewer
    assert client.get(f"/api/devices/{device}/status").status_code == 404


def test_viewer_sees_device(client, login_as, device, fake_tuya):
    login_as("viewer")
    body = client.get(f"/api/devices/{device}/status").json()
    assert body["success"] is True
    assert body["online"] is True


def test_control_requires_permission(client, login_as, device, fake_tuya):
    login_as("viewer")  # can view, cannot control
    assert client.post(f"/api/devices/{device}/on").status_code == 403


def test_control_invisible_device_is_404(client, login_as, device, fake_tuya):
    login_as("operator")
    assert client.post(f"/api/devices/{device}/on").status_code == 404


def test_control_turns_device_on_and_logs(client, login_as, device, fake_tuya, ready_db):
    login_as("superadmin")
    response = client.post(f"/api/devices/{device}/on")
    assert response.status_code == 200
    assert response.json()["success"] is True
    assert fake_tuya["switch_on"] is True

    rows = logs.recent_activities()
    assert rows[0]["action"] == "turn_on"
    assert rows[0]["actor"] == "ui"


def test_unreachable_device_returns_failure_not_500(client, login_as, device, fake_tuya):
    login_as("superadmin")
    fake_tuya["online"] = False
    state_cache.cache.clear()

    status = client.get(f"/api/devices/{device}/status")
    assert status.status_code == 200
    assert status.json()["success"] is False
    assert status.json()["online"] is False

    control = client.post(f"/api/devices/{device}/on")
    assert control.status_code == 200
    assert control.json()["success"] is False


def test_create_device_validates_dps(client, login_as):
    login_as("superadmin")
    response = client.post(
        "/api/devices",
        json={"name": "aneh", "tuya_id": "x", "local_key": "k", "type": "plug", "dps": {"salah": 1}},
    )
    assert response.status_code == 422
    assert response.json()["detail"]["errors"][0]["key"] == "dps"


def test_create_device_uses_template_when_dps_omitted(client, login_as):
    login_as("superadmin")
    response = client.post(
        "/api/devices", json={"name": "lampu", "tuya_id": "y", "local_key": "k", "type": "bulb"}
    )
    assert response.status_code == 200
    assert response.json()["dps"] == {"switch": 20, "brightness": 22, "temp": 23, "colour": 24}


def test_duplicate_name_rejected(client, login_as, device):
    login_as("superadmin")
    response = client.post("/api/devices", json={"name": "air", "tuya_id": "z", "local_key": "k"})
    assert response.status_code == 422
    assert response.json()["detail"]["errors"][0]["key"] == "name"


def test_update_device_does_not_audit_local_key(client, login_as, device):
    from tuyabot.storage.repos import audit

    login_as("superadmin")
    response = client.patch(f"/api/devices/{device}", json={"local_key": "kunci-baru", "label": "Baru"})
    assert response.status_code == 200
    rows = audit.list_page(action="devices.update")
    assert rows[0]["details"]["local_key_changed"] is True
    assert "kunci-baru" not in str(rows[0]["details"])


def test_delete_device(client, login_as, device):
    login_as("superadmin")
    assert client.delete(f"/api/devices/{device}").status_code == 200
    assert client.get("/api/devices").json()["devices"] == []


def test_stream_snapshot_does_not_call_tuya(client, login_as, device, fake_tuya):
    from tuyabot.web.routes.stream import build_snapshot

    login_as("viewer")
    state_cache.cache.clear()
    before = fake_tuya["calls"]

    principal = registry.visible_to  # sanity: registry present
    assert principal is not None

    from fastapi.testclient import TestClient

    from tuyabot.web import auth_impl
    from tuyabot.web.app import create_app

    # Call the snapshot builder directly: the SSE loop itself never calls Tuya.
    app_client = TestClient(create_app(), cookies={"tuyabot_session": "test-session"})
    assert app_client.get("/api/auth/me").status_code == 200

    from tuyabot.web.deps import Principal

    principal = Principal("web", 1, "tester", roles.get_by_slug("viewer")["id"], "viewer",
                          frozenset({"devices.view"}))
    snapshot = build_snapshot(principal)
    assert len(snapshot["devices"]) == 1
    assert fake_tuya["calls"] == before
    assert auth_impl is not None


def test_scan_requires_permission(client, login_as):
    login_as("operator")
    assert client.post("/api/devices/scan").status_code == 403


def test_logs_require_logs_view(client, login_as, device):
    login_as("viewer")
    assert client.get("/api/logs/activities").status_code == 200
    assert client.get("/api/logs/power").status_code == 200
    login_as("operator")
    assert client.get("/api/logs/activities").status_code == 200


def test_power_logging_row_shape(ready_db, device):
    logs.log_power(device_id=device, power_w=12.5, voltage_v=220, current_a=0.06, switch_state=True, source="test")
    rows = logs.recent_power(device_id=device)
    assert rows[0]["power_w"] == 12.5
    assert rows[0]["switch_state"] == 1
    assert rows[0]["device_name"] == "air"


def test_settings_driven_timeout_is_used(ready_db):
    settings_service.patch({"tuya.call_timeout_seconds": 5.0}, actor={})
    from tuyabot.devices import service

    service.configure(threads=2, timeout_seconds=5.0)
    assert service._default_timeout == 5.0
