"""A role that can switch the device off must never arm the watchdog.

registry.can_control grants control to any role holding manage_devices, without
a role_device_access row. should_arm must agree with that, otherwise it arms a
watchdog against an actor who could have switched the device off themselves.
"""

from tuyabot.storage.repos import devices as devices_repo
from tuyabot.storage.repos import roles
from tuyabot.telegram import watchdog as watchdog_module


def test_a_manager_does_not_arm_the_watchdog(ready_db):
    device_id = devices_repo.create(
        {
            "name": "pompa",
            "label": "Pompa",
            "tuya_id": "t1",
            "local_key": "k",
            "type": "plug",
            "features": {"watchdog": True},
        }
    )
    # Superadmin holds manage_devices and has no role_device_access row.
    superadmin = roles.get_by_slug("superadmin")["id"]

    assert watchdog_module.watchdog.should_arm(devices_repo.get(device_id), superadmin) is False


def test_a_role_without_manage_or_off_still_arms(ready_db):
    from tuyabot.storage.repos import role_devices

    device_id = devices_repo.create(
        {
            "name": "pompa",
            "label": "Pompa",
            "tuya_id": "t1",
            "local_key": "k",
            "type": "plug",
            "features": {"watchdog": True},
        }
    )
    role_id = roles.create("ononly", "On only", None, [])
    role_devices.set_for_role(
        role_id, [{"device_id": device_id, "can_view": True, "can_on": True, "can_off": False}]
    )

    assert watchdog_module.watchdog.should_arm(devices_repo.get(device_id), role_id) is True
