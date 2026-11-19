"""Every inline button must do something.

The menu is generated from the role's rights, so a button that dispatches to
nothing is worse than a missing one: the user taps it, the spinner stops, and
nothing happens.
"""

import asyncio
from typing import Any

from tuyabot.storage.repos import devices as devices_repo
from tuyabot.storage.repos import role_devices, roles, telegram_users
from tuyabot.telegram import handlers


class FakeQuery:
    def __init__(self, data: str) -> None:
        self.data = data
        self.answered = False
        self.edits: list[str] = []

    async def answer(self) -> None:
        self.answered = True

    async def edit_message_text(self, text, **kwargs):
        self.edits.append(text)


class FakeMessage:
    def __init__(self) -> None:
        self.sent: list[str] = []

    async def reply_text(self, text, **kwargs):
        self.sent.append(text)


class FakeUpdate:
    def __init__(self, data: str, user_id: int) -> None:
        self.callback_query = FakeQuery(data)
        self.effective_message = FakeMessage()
        self.effective_user = type("U", (), {"id": user_id})()


class FakeContext:
    def __init__(self, telegram_id: int, args: list[str] | None = None) -> None:
        from tuyabot.telegram import guards

        self.user_data = {"principal": guards.resolve(telegram_id)}
        self.args = args or []
        self.bot = None


def _setup_role(device_id: int, **rights: bool) -> int:
    role_id = roles.create("tombol", "Tombol", None, ["monitoring", "manage_users"])
    role_devices.set_for_role(role_id, [{"device_id": device_id, **rights}])
    return role_id


def _device() -> int:
    return devices_repo.create(
        {"name": "pompa", "label": "Pompa", "tuya_id": "t1", "local_key": "k", "type": "plug"}
    )


def test_every_button_the_keyboard_offers_is_dispatched(ready_db):
    """The keyboard's callback_data values must all be handled."""
    device_id = _device()
    role_id = _setup_role(device_id, can_view=True, can_on=True, can_off=True)
    telegram_users.upsert(8001, role_id, label="Budi")
    context = FakeContext(8001)
    principal = context.user_data["principal"]

    keyboard = handlers._main_keyboard(principal)
    offered = {
        button.callback_data
        for row in keyboard.inline_keyboard
        for button in row
    }

    handled = handlers.handled_callbacks()
    unhandled = [
        data
        for data in offered
        if data not in handled and not any(data.startswith(prefix) for prefix in handled)
    ]
    assert unhandled == [], f"tombol tanpa handler: {sorted(unhandled)}"


def test_tapping_account_replies(ready_db):
    device_id = _device()
    role_id = _setup_role(device_id, can_view=True, can_on=True, can_off=True)
    telegram_users.upsert(8002, role_id, label="Budi")
    update = FakeUpdate("whoami", 8002)

    asyncio.run(handlers.callback(update, FakeContext(8002)))

    assert update.callback_query.answered is True
    assert update.effective_message.sent, "tombol Akun Saya tidak mengirim balasan"


def test_tapping_an_on_button_switches_the_device(ready_db, monkeypatch):
    device_id = _device()
    role_id = _setup_role(device_id, can_view=True, can_on=True, can_off=False)
    telegram_users.upsert(8003, role_id, label="Budi")
    calls: list[Any] = []

    async def fake_run(fn, device, on=None, **kwargs):
        # switch_state is called without an "on" value.
        if on is None:
            return True
        calls.append((device["name"], on))
        return {"success": True}

    async def fake_status(device, force=False):
        return {"success": True, "switch_on": True}

    monkeypatch.setattr("tuyabot.devices.service.run_tuya", fake_run)
    monkeypatch.setattr("tuyabot.infra.state_cache.get_status", fake_status)
    update = FakeUpdate("on:pompa", 8003)

    asyncio.run(handlers.callback(update, FakeContext(8003)))

    assert calls == [("pompa", True)]


def test_an_off_button_is_refused_for_a_role_that_has_no_off_right(ready_db, monkeypatch):
    device_id = _device()
    role_id = _setup_role(device_id, can_view=True, can_on=True, can_off=False)
    telegram_users.upsert(8004, role_id, label="Budi")
    calls: list[Any] = []

    async def fake_run(fn, device, on=None, **kwargs):
        if on is None:
            return True
        calls.append(on)
        return {"success": True}

    async def fake_status(device, force=False):
        return {"success": True, "switch_on": True}

    monkeypatch.setattr("tuyabot.devices.service.run_tuya", fake_run)
    monkeypatch.setattr("tuyabot.infra.state_cache.get_status", fake_status)
    update = FakeUpdate("off:pompa", 8004)

    asyncio.run(handlers.callback(update, FakeContext(8004)))

    assert calls == [], "role tanpa hak matikan tidak boleh mengirim perintah mati"


def test_the_menu_offers_only_the_actions_the_role_holds(ready_db):
    device_id = _device()
    role_id = _setup_role(device_id, can_view=True, can_on=True, can_off=False)
    telegram_users.upsert(8005, role_id, label="Budi")
    context = FakeContext(8005)

    keyboard = handlers._main_keyboard(context.user_data["principal"])
    offered = [button.callback_data for row in keyboard.inline_keyboard for button in row]

    assert "on:pompa" in offered
    assert "off:pompa" not in offered, "role tanpa hak matikan tidak boleh ditawari tombol matikan"
