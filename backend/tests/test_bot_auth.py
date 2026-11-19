from tuyabot.access import bot_auth
from tuyabot.storage.repos import devices as devices_repo
from tuyabot.storage.repos import role_devices, roles


def test_unknown_role_has_nothing(ready_db):
    assert bot_auth.can(None, "monitoring") is False
    assert bot_auth.can_device(None, 1, "on") is False


def test_permission_comes_from_role(ready_db):
    role_id = roles.create("uji", "Uji", None, ["monitoring"])
    assert bot_auth.can(role_id, "monitoring") is True
    assert bot_auth.can(role_id, "manage_users") is False


def test_on_and_off_are_separate(ready_db):
    role_id = roles.create("uji", "Uji", None, [])
    device_id = devices_repo.create({"name": "pompa", "label": "Pompa", "tuya_id": "t1", "local_key": "k"})
    role_devices.set_for_role(role_id, [
        {"device_id": device_id, "can_view": True, "can_on": True, "can_off": False}
    ])

    assert bot_auth.can_device(role_id, device_id, "on") is True
    assert bot_auth.can_device(role_id, device_id, "off") is False
    assert bot_auth.can_device(role_id, device_id, "view") is True


def test_a_device_without_a_row_is_not_reachable(ready_db):
    role_id = roles.create("uji", "Uji", None, [])
    device_id = devices_repo.create({"name": "pompa", "label": "Pompa", "tuya_id": "t1", "local_key": "k"})
    assert bot_auth.can_device(role_id, device_id, "view") is False


def test_an_unknown_action_is_refused(ready_db):
    """A typo in a caller must not fall through to an allowance."""
    role_id = roles.create("uji", "Uji", None, [])
    device_id = devices_repo.create({"name": "pompa", "label": "Pompa", "tuya_id": "t1", "local_key": "k"})
    role_devices.set_for_role(role_id, [
        {"device_id": device_id, "can_view": True, "can_on": True, "can_off": True}
    ])

    assert bot_auth.can_device(role_id, device_id, "delete") is False
