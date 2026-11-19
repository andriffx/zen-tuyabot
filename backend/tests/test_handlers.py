"""Handler behaviour with a fake Telegram update; no network."""

import pytest

from tuyabot.devices import controller as controller_module
from tuyabot.devices import registry
from tuyabot.storage.repos import devices as devices_repo
from tuyabot.storage.repos import roles, telegram_users
from tuyabot.telegram import guards, handlers


class FakeMessage:
    def __init__(self) -> None:
        self.sent: list[str] = []

    async def reply_text(self, text, **kwargs):
        self.sent.append(text)


class FakeUser:
    def __init__(self, user_id: int) -> None:
        self.id = user_id


class FakeUpdate:
    def __init__(self, user_id: int) -> None:
        self.effective_user = FakeUser(user_id)
        self.effective_message = FakeMessage()


class FakeContext:
    def __init__(self, telegram_id: int, args: list[str] | None = None) -> None:
        self.user_data = {"principal": guards.resolve(telegram_id)}
        self.args = args or []


def _role(slug: str) -> int:
    return roles.get_by_slug(slug)["id"]


@pytest.fixture()
def device(ready_db):
    device_id = devices_repo.create(
        {"name": "pompa", "label": "Pompa", "tuya_id": "d1", "local_key": "k", "type": "plug"}
    )
    registry.reload()
    yield device_id
    registry.reset_cache()


def grant(slug: str, device_id: int, *, view=True, on=True, off=True) -> None:
    """Give a role access to a device. Access is per role and per device now."""
    from tuyabot.storage.repos import role_devices

    role_id = roles.get_by_slug(slug)["id"]
    role_devices.set_for_role(role_id, [
        {"device_id": device_id, "can_view": view, "can_on": on, "can_off": off}
    ])


@pytest.fixture()
def fake_switch(monkeypatch):
    state = {"on": False, "calls": 0}

    def set_switch(device, on):
        state["calls"] += 1
        state["on"] = on
        return {"success": True}

    async def status(device, force=False):
        return {"success": True, "switch_on": state["on"], "power_w": 5.0}

    def switch_state(device):
        # The bot verifies the DP after a control command, as the web path does.
        return state["on"]

    monkeypatch.setattr(controller_module.controller, "set_switch", set_switch)
    monkeypatch.setattr(controller_module.controller, "switch_state", switch_state)
    monkeypatch.setattr("tuyabot.infra.state_cache.get_status", status)
    return state


def test_unregistered_user_only_gets_public_commands(ready_db):
    update = FakeUpdate(1000)
    context = FakeContext(1000)
    assert context.user_data["principal"] is None

    import asyncio

    asyncio.run(handlers.devices_command(update, context))
    assert "tidak memiliki izin" in update.effective_message.sent[0].lower()


def test_registered_operator_can_toggle_device(device, fake_switch):
    grant("operator", device)
    telegram_users.upsert(2001, _role("operator"))
    update = FakeUpdate(2001)
    context = FakeContext(2001, ["pompa"])

    import asyncio

    asyncio.run(handlers.on_command(update, context))
    assert fake_switch["calls"] == 1
    assert fake_switch["on"] is True
    assert "dinyalakan" in update.effective_message.sent[-1]


def test_viewer_cannot_toggle(device, fake_switch):
    from tuyabot.storage.repos import audit

    # View only: no can_on, so the toggle must be refused.
    grant("viewer", device, on=False, off=False)
    telegram_users.upsert(2002, _role("viewer"))
    update = FakeUpdate(2002)
    context = FakeContext(2002, ["pompa"])

    import asyncio

    asyncio.run(handlers.on_command(update, context))
    assert fake_switch["calls"] == 0
    assert "tidak memiliki akses" in update.effective_message.sent[0].lower()
    assert audit.list_page(action="access.denied", result="denied")


def test_adduser_enforces_subset(device):
    from tuyabot.storage.repos import roles as roles_repo

    # A role that may manage Telegram users but holds fewer rights than
    # superadmin: it must not be able to grant that role.
    manager_role = roles_repo.get_by_slug("operator")
    roles_repo.update(manager_role["id"], permissions=["manage_users"])
    telegram_users.upsert(3000, manager_role["id"])
    update = FakeUpdate(3000)
    context = FakeContext(3000, ["9999", "superadmin"])

    import asyncio

    asyncio.run(handlers.adduser_command(update, context))
    assert telegram_users.get(9999) is None
    assert "Tidak boleh" in update.effective_message.sent[-1]


def test_adduser_creates_telegram_user_only(device):
    from tuyabot.storage.repos import web_users

    telegram_users.upsert(3001, _role("superadmin"))
    update = FakeUpdate(3001)
    context = FakeContext(3001, ["4004", "operator"])

    import asyncio

    asyncio.run(handlers.adduser_command(update, context))
    created = telegram_users.get(4004)
    assert created is not None
    assert created["role_slug"] == "operator"
    assert web_users.list_all() == []


def test_status_lists_only_visible_devices(device, fake_switch):
    viewer = _role("viewer")
    grant("viewer", device)  # only "pompa" is visible to this role
    devices_repo.create(
        {
            "name": "rahasia",
            "label": "Rahasia",
            "tuya_id": "d2",
            "local_key": "k",
            "type": "plug",
        }
    )
    registry.reload()
    telegram_users.upsert(5000, viewer)

    update = FakeUpdate(5000)
    context = FakeContext(5000)
    import asyncio

    asyncio.run(handlers.status_command(update, context))
    text = update.effective_message.sent[-1]
    assert "Pompa" in text
    assert "Rahasia" not in text


def test_help_adapts_to_permissions(device):
    grant("viewer", device, on=False, off=False)
    telegram_users.upsert(6000, _role("viewer"))
    update = FakeUpdate(6000)
    context = FakeContext(6000)

    import asyncio

    asyncio.run(handlers.help_command(update, context))
    text = update.effective_message.sent[-1]
    assert "/devices" in text
    assert "/adduser" not in text


def test_start_for_unregistered_user_explains(ready_db):
    update = FakeUpdate(7000)
    context = FakeContext(7000)

    import asyncio

    asyncio.run(handlers.start(update, context))
    # Text comes from the editable deny.public template.
    text = update.effective_message.sent[-1].lower()
    assert "tidak" in text or "belum" in text
    assert "7000" in update.effective_message.sent[-1]
