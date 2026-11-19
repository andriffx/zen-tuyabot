"""The auto-off notice must go to a Telegram chat, never to a web user id.

A dashboard session's actor_id is a web_users row id and an API key's is an
api_keys row id. Neither is a chat: sending to it usually fails, and if some
Telegram account happens to own that number, a stranger receives a notice about
the pump in this house.
"""

import asyncio

import pytest

from tuyabot.storage.repos import devices as devices_repo
from tuyabot.telegram import watchdog as watchdog_module


class FakeManager:
    def __init__(self) -> None:
        self.sent: list[tuple[int, str]] = []

    async def send(self, chat_id, text):
        self.sent.append((chat_id, text))
        return True


@pytest.fixture()
def device(ready_db):
    device_id = devices_repo.create(
        {"name": "pompa", "label": "Pompa", "tuya_id": "t1", "local_key": "k",
         "type": "plug", "features": {"watchdog": True}}
    )
    return devices_repo.get(device_id)


def _capture(monkeypatch):
    fake = FakeManager()
    monkeypatch.setattr("tuyabot.telegram.manager.manager", fake)
    return fake


def test_a_web_actor_gets_no_telegram_direct_message(device, monkeypatch):
    fake = _capture(monkeypatch)
    dog = watchdog_module.Watchdog()
    dog._state[device["id"]] = {
        "running": True, "device": "pompa", "user_id": 1, "user_name": "Superadmin",
        "actor_kind": "web",
    }

    asyncio.run(dog._notify(device, "idle", "idle di bawah 200W", True, 30, 12.5))

    chat_ids = [chat for chat, _ in fake.sent]
    assert 1 not in chat_ids, "notifikasi dikirim ke chat id 1 milik orang lain"


def test_a_telegram_actor_is_notified(device, monkeypatch):
    fake = _capture(monkeypatch)
    dog = watchdog_module.Watchdog()
    dog._state[device["id"]] = {
        "running": True, "device": "pompa", "user_id": 555, "user_name": "Budi",
        "actor_kind": "telegram",
    }

    asyncio.run(dog._notify(device, "idle", "idle di bawah 200W", True, 30, 12.5))

    assert any(chat == 555 for chat, _ in fake.sent)


def test_the_actor_kind_travels_into_the_armed_state(device, monkeypatch):
    """arm() must record the kind, so _notify can tell a chat from a row id."""
    class FakeTask:
        def done(self):
            return True

    monkeypatch.setattr(watchdog_module.asyncio, "create_task", lambda coro, **kw: FakeTask())
    dog = watchdog_module.Watchdog()

    dog.arm(device, user_id=555, user_name="Budi", actor_kind="telegram")
    assert dog._state[device["id"]]["actor_kind"] == "telegram"

    dog.arm(device, user_id=1, user_name="Superadmin", actor_kind="web")
    assert dog._state[device["id"]]["actor_kind"] == "web"
