"""The watchdog arms from the ability to switch off, not from a role list."""

from tuyabot.storage.repos import devices as devices_repo
from tuyabot.storage.repos import role_devices, roles
from tuyabot.telegram import watchdog as watchdog_module


def _device(*, watchdog_feature: bool = True) -> int:
    return devices_repo.create(
        {
            "name": "pompa",
            "label": "Pompa",
            "tuya_id": "t1",
            "local_key": "k",
            "type": "plug",
            "features": {"watchdog": watchdog_feature},
        }
    )


def _role_with(device_id: int, *, on: bool, off: bool) -> int:
    role_id = roles.create(f"r{on}{off}", "R", None, [])
    role_devices.set_for_role(
        role_id, [{"device_id": device_id, "can_view": True, "can_on": on, "can_off": off}]
    )
    return role_id


def test_a_role_that_cannot_switch_off_arms_the_watchdog(ready_db):
    device_id = _device()
    role_id = _role_with(device_id, on=True, off=False)

    assert watchdog_module.watchdog.should_arm(devices_repo.get(device_id), role_id) is True


def test_a_role_that_can_switch_off_does_not_arm_it(ready_db):
    device_id = _device()
    role_id = _role_with(device_id, on=True, off=True)

    assert watchdog_module.watchdog.should_arm(devices_repo.get(device_id), role_id) is False


def test_a_device_without_the_feature_never_arms(ready_db):
    device_id = _device(watchdog_feature=False)
    role_id = _role_with(device_id, on=True, off=False)

    assert watchdog_module.watchdog.should_arm(devices_repo.get(device_id), role_id) is False


def test_an_unknown_role_never_arms(ready_db):
    device_id = _device()

    assert watchdog_module.watchdog.should_arm(devices_repo.get(device_id), None) is False
