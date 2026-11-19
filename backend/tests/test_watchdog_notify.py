"""Auto-off must tell the truth about what happened."""

import asyncio

import pytest

from tuyabot.storage.repos import devices as devices_repo
from tuyabot.telegram import watchdog as watchdog_module


class FakeManager:
    def __init__(self) -> None:
        self.sent: list[tuple[int, str]] = []
        self.fail = False

    async def send(self, chat_id, text):
        self.sent.append((chat_id, text))
        return not self.fail


def _dog(device_id: int) -> watchdog_module.Watchdog:
    dog = watchdog_module.Watchdog()
    dog._state[device_id] = {"running": True, "device": "pompa", "user_id": 555, "user_name": "Budi"}
    return dog


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


def test_an_idle_cutoff_uses_the_idle_template(device, monkeypatch):
    fake = _capture(monkeypatch)
    dog = _dog(device["id"])

    asyncio.run(dog._notify(device, "idle", "idle di bawah 200W", True, 30, 12.5))

    user_text = next(text for chat, text in fake.sent if chat == 555)
    assert "tidak digunakan" in user_text.lower()
    assert "12.5" in user_text


def test_a_max_duration_cutoff_uses_the_duration_template(device, monkeypatch):
    fake = _capture(monkeypatch)
    dog = _dog(device["id"])

    asyncio.run(dog._notify(device, "max_time", "melewati batas 30 menit", True, 30, 0.0))

    user_text = next(text for chat, text in fake.sent if chat == 555)
    assert "30 menit" in user_text


def test_a_failed_switch_off_is_not_reported_as_done(device, monkeypatch):
    fake = _capture(monkeypatch)
    dog = _dog(device["id"])

    asyncio.run(dog._notify(device, "idle", "idle di bawah 200W", False, 30, 12.5))

    user_text = next(text for chat, text in fake.sent if chat == 555)
    assert "gagal dimatikan" in user_text.lower()
    assert "telah dinonaktifkan" not in user_text.lower()
