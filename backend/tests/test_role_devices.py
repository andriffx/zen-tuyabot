from tuyabot.storage.repos import devices as devices_repo
from tuyabot.storage.repos import role_devices, roles


def test_set_and_read_back(ready_db):
    role_id = roles.create("uji", "Uji", None, ["monitoring"])
    device_id = devices_repo.create({"name": "pompa", "label": "Pompa", "tuya_id": "t1", "local_key": "k"})

    role_devices.set_for_role(role_id, [
        {"device_id": device_id, "can_view": True, "can_on": True, "can_off": False}
    ])

    assert role_devices.get_for_role(role_id) == [
        {"device_id": device_id, "can_view": True, "can_on": True, "can_off": False}
    ]


def test_set_replaces_previous_rows(ready_db):
    role_id = roles.create("uji", "Uji", None, [])
    device_id = devices_repo.create({"name": "pompa", "label": "Pompa", "tuya_id": "t1", "local_key": "k"})

    role_devices.set_for_role(role_id, [{"device_id": device_id, "can_view": True, "can_on": True, "can_off": True}])
    role_devices.set_for_role(role_id, [])

    assert role_devices.get_for_role(role_id) == []


def test_deleting_a_device_removes_its_access_rows(ready_db):
    role_id = roles.create("uji", "Uji", None, [])
    device_id = devices_repo.create({"name": "pompa", "label": "Pompa", "tuya_id": "t1", "local_key": "k"})
    role_devices.set_for_role(role_id, [{"device_id": device_id, "can_view": True, "can_on": True, "can_off": True}])

    devices_repo.delete(device_id)

    assert role_devices.get_for_role(role_id) == []
