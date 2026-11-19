"""Role device matrix: one row per role/device pair, three separate rights."""

from tuyabot.storage.repos import devices as devices_repo
from tuyabot.storage.repos import role_devices, roles


def _role(ready_db) -> int:
    return roles.create("uji", "Uji", None, ["monitoring"])


def _devices(count: int) -> list[int]:
    return [
        devices_repo.create({"name": f"d{i}", "label": f"D{i}", "tuya_id": f"t{i}", "local_key": "k"})
        for i in range(count)
    ]


def test_put_replaces_the_whole_matrix(client, csrf_value, login_as, ready_db):
    login_as("superadmin")
    role_id = _role(ready_db)
    first, second = _devices(2)

    client.put(
        f"/api/roles/{role_id}/devices",
        json={"entries": [
            {"device_id": first, "can_view": True, "can_on": True, "can_off": False},
            {"device_id": second, "can_view": True, "can_on": False, "can_off": False},
        ]},
        headers={"X-CSRF-Token": csrf_value},
    )
    response = client.put(
        f"/api/roles/{role_id}/devices",
        json={"entries": [
            {"device_id": first, "can_view": True, "can_on": False, "can_off": True},
        ]},
        headers={"X-CSRF-Token": csrf_value},
    )

    assert response.status_code == 200
    remaining = role_devices.get_for_role(role_id)
    assert remaining == [
        {"device_id": first, "can_view": True, "can_on": False, "can_off": True}
    ]


def test_get_lists_the_matrix(client, login_as, ready_db):
    login_as("superadmin")
    role_id = _role(ready_db)
    (device_id,) = _devices(1)
    role_devices.set_for_role(
        role_id, [{"device_id": device_id, "can_view": True, "can_on": True, "can_off": False}]
    )

    body = client.get(f"/api/roles/{role_id}/devices").json()

    assert body["entries"] == [
        {"device_id": device_id, "can_view": True, "can_on": True, "can_off": False}
    ]


def test_put_refuses_an_unknown_device(client, csrf_value, login_as, ready_db):
    login_as("superadmin")
    role_id = _role(ready_db)

    response = client.put(
        f"/api/roles/{role_id}/devices",
        json={"entries": [{"device_id": 99999, "can_view": True, "can_on": True, "can_off": True}]},
        headers={"X-CSRF-Token": csrf_value},
    )

    assert response.status_code == 422
    assert role_devices.get_for_role(role_id) == []


def test_put_refuses_a_duplicate_device(client, csrf_value, login_as, ready_db):
    login_as("superadmin")
    role_id = _role(ready_db)
    (device_id,) = _devices(1)
    entry = {"device_id": device_id, "can_view": True, "can_on": True, "can_off": True}

    response = client.put(
        f"/api/roles/{role_id}/devices",
        json={"entries": [entry, entry]},
        headers={"X-CSRF-Token": csrf_value},
    )

    assert response.status_code == 422
