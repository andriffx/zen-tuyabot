"""Even an unregistered user gets a menu.

The reference shows PUBLIC a keyboard with "Akun Saya" and "Bantuan": those
actions need no permission, so withholding the whole menu because the user has
no device is wrong. "/start" must never promise a menu it does not attach.
"""

import asyncio

from tuyabot.storage.repos import devices as devices_repo
from tuyabot.storage.repos import role_devices, roles, telegram_users
from tuyabot.telegram import handlers


class FakeMessage:
    def __init__(self) -> None:
        self.sent: list[str] = []
        self.markup = None

    async def reply_text(self, text, **kwargs):
        self.sent.append(text)
        self.markup = kwargs.get("reply_markup")


class FakeUpdate:
    def __init__(self, user_id: int) -> None:
        self.effective_user = type("U", (), {"id": user_id, "first_name": "Tamu"})()
        self.effective_message = FakeMessage()


class FakeContext:
    def __init__(self, telegram_id: int) -> None:
        from tuyabot.telegram import guards

        self.user_data = {"principal": guards.resolve(telegram_id)}
        self.args = []
        self.bot = None


def _buttons(markup) -> list[str]:
    return [button.callback_data for row in markup.inline_keyboard for button in row]


def test_a_public_user_still_gets_a_menu(ready_db):
    """No role, no device — and still a keyboard."""
    update = FakeUpdate(5555)

    asyncio.run(handlers.start(update, FakeContext(5555)))

    markup = update.effective_message.markup
    assert markup is not None, "/start untuk publik tidak mengirim menu"
    assert "whoami" in _buttons(markup)
    assert "help" in _buttons(markup)


def test_a_registered_role_without_devices_also_gets_the_menu(ready_db):
    role_id = roles.create("kosong", "Kosong", None, [])
    telegram_users.upsert(5556, role_id, label="Budi")
    update = FakeUpdate(5556)

    asyncio.run(handlers.start(update, FakeContext(5556)))

    markup = update.effective_message.markup
    assert markup is not None
    assert "whoami" in _buttons(markup)


def test_device_buttons_appear_only_with_access(ready_db):
    role_id = roles.create("punya", "Punya", None, ["monitoring"])
    device_id = devices_repo.create(
        {"name": "pompa", "label": "Pompa", "tuya_id": "t1", "local_key": "k", "type": "plug"}
    )
    role_devices.set_for_role(
        role_id, [{"device_id": device_id, "can_view": True, "can_on": True, "can_off": False}]
    )
    telegram_users.upsert(5557, role_id, label="Budi")
    update = FakeUpdate(5557)

    asyncio.run(handlers.start(update, FakeContext(5557)))

    buttons = _buttons(update.effective_message.markup)
    assert "on:pompa" in buttons
    assert "devices" in buttons
