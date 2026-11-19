"""Device visibility and control now come from role_device_access.

The old rule read `devices.access_roles` plus web permission keys
(`devices.view`, `devices.control`). Both are gone: access is per role and per
device, with `on` and `off` decided independently.
"""

from tuyabot.devices import registry
from tuyabot.storage.repos import devices as devices_repo
from tuyabot.storage.repos import role_devices, roles
from tuyabot.web.deps import Principal


def _principal(role_id: int, slug: str = "uji") -> Principal:
    return Principal(
        actor_kind="web",
        actor_id=None,
        label="tester",
        role_id=role_id,
        role_slug=slug,
        permissions=frozenset(),
        session_token=None,
    )


def _device(name: str) -> int:
    return devices_repo.create(
        {"name": name, "label": name, "tuya_id": f"id-{name}", "local_key": "k"}
    )


def test_a_device_without_a_row_is_invisible(ready_db):
    role_id = roles.create("uji", "Uji", None, [])
    device_id = _device("pompa")
    principal = _principal(role_id)

    assert registry.can_view(principal, registry.get(device_id)) is False
    assert registry.visible_to(principal) == []


def test_can_view_grants_visibility_but_not_control(ready_db):
    role_id = roles.create("uji", "Uji", None, [])
    device_id = _device("pompa")
    role_devices.set_for_role(
        role_id, [{"device_id": device_id, "can_view": True, "can_on": False, "can_off": False}]
    )
    principal = _principal(role_id)
    device = registry.get(device_id)

    assert registry.can_view(principal, device) is True
    assert registry.can_control(principal, device) is False


def test_can_on_allows_switching_on_but_not_off(ready_db):
    role_id = roles.create("uji", "Uji", None, [])
    device_id = _device("pompa")
    role_devices.set_for_role(
        role_id, [{"device_id": device_id, "can_view": True, "can_on": True, "can_off": False}]
    )
    principal = _principal(role_id)
    device = registry.get(device_id)

    assert registry.can_control(principal, device) is True
    assert registry.can_control(principal, device, "on") is True
    assert registry.can_control(principal, device, "off") is False


def test_access_roles_on_the_device_grants_nothing(ready_db):
    """The deprecated column must not authorize anyone any more."""
    role_id = roles.create("uji", "Uji", None, [])
    device_id = devices_repo.create({
        "name": "pompa", "label": "pompa", "tuya_id": "t1", "local_key": "k",
        "access_roles": [role_id],
    })
    principal = _principal(role_id)

    assert registry.can_view(principal, registry.get(device_id)) is False


def test_a_principal_without_a_role_sees_nothing(ready_db):
    device_id = _device("pompa")
    anonymous = Principal("system", None, None, None, None, frozenset())

    assert registry.can_view(anonymous, registry.get(device_id)) is False
    assert registry.visible_to(anonymous) == []
