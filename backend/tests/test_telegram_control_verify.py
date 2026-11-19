"""The bot must verify the switch moved, exactly as the web path does.

A Tuya plug acknowledges a well-formed frame even when the DP does not apply.
Reporting "berhasil dinyalakan" from the ACK alone is the bug already fixed for
the dashboard; the bot path kept the old behaviour.
"""

import asyncio

import pytest

from tuyabot.storage.repos import devices as devices_repo
from tuyabot.storage.repos import role_devices, roles, telegram_users
from tuyabot.telegram import handlers


class FakeMessage:
    def __init__(self) -> None:
        self.sent: list[str] = []

    async def reply_text(self, text, **kwargs):
        self.sent.append(text)


class FakeUpdate:
    def __init__(self, user_id: int) -> None:
        self.effective_user = type("U", (), {"id": user_id})()
        self.effective_message = FakeMessage()


class FakeContext:
    def __init__(self, telegram_id: int, args: list[str]) -> None:
        from tuyabot.telegram import guards

        self.user_data = {"principal": guards.resolve(telegram_id)}
        self.args = args
        self.bot = None


@pytest.fixture()
def device(ready_db):
    device_id = devices_repo.create(
        {"name": "pompa", "label": "Pompa", "tuya_id": "t1", "local_key": "k", "type": "plug"}
    )
    role_id = roles.create("user2", "User", None, ["monitoring"])
    role_devices.set_for_role(
        role_id, [{"device_id": device_id, "can_view": True, "can_on": True, "can_off": True}]
    )
    telegram_users.upsert(9001, role_id, label="Budi")
    return device_id


def _fake_tuya(monkeypatch, *, switch_after: bool):
    async def fake_run(fn, device, on=None, **kwargs):
        # set_switch is called with on; switch_state is called without.
        if on is None:
            return switch_after
        return {"success": True, "ack": "null"}

    async def fake_status(device, force=False):
        return {"success": True, "switch_on": switch_after}

    monkeypatch.setattr("tuyabot.devices.service.run_tuya", fake_run)
    monkeypatch.setattr("tuyabot.infra.state_cache.get_status", fake_status)
    monkeypatch.setattr("tuyabot.infra.state_cache.cache", type("C", (), {"invalidate": lambda *a: None})())


def test_a_command_that_did_not_change_the_switch_is_reported_as_failure(device, monkeypatch):
    _fake_tuya(monkeypatch, switch_after=False)
    update = FakeUpdate(9001)

    asyncio.run(handlers._toggle(update, FakeContext(9001, ["pompa"]), True))

    text = update.effective_message.sent[-1].lower()
    assert "berhasil" not in text
    assert "tidak berubah" in text or "gagal" in text


def test_a_command_that_did_change_the_switch_is_reported_as_success(device, monkeypatch):
    _fake_tuya(monkeypatch, switch_after=True)
    update = FakeUpdate(9001)

    asyncio.run(handlers._toggle(update, FakeContext(9001, ["pompa"]), True))

    text = update.effective_message.sent[-1].lower()
    assert "berhasil" in text
