"""Bot manager: independent lifecycles, duplicate tokens, rebuilds."""

import asyncio
from typing import ClassVar

import pytest

from tuyabot.storage.repos import bots as bots_repo
from tuyabot.telegram import manager as manager_module


class FakeApplication:
    """Stands in for telegram.ext.Application. Never contacts Telegram."""

    instances: ClassVar[list["FakeApplication"]] = []
    fail_tokens: ClassVar[set[str]] = set()

    def __init__(self, token: str) -> None:
        self.token = token
        self.started = False
        self.stopped = False
        self.updated_polling = False
        class _Bot:
            username = "test_bot"
        self.bot = _Bot()
        self.updater = self

    async def initialize(self):
        if self.token in self.fail_tokens:
            raise RuntimeError("Conflict: terminated by other getUpdates request")
        self.initialized = True

    async def start(self):
        self.started = True

    async def stop(self):
        self.stopped = True

    async def shutdown(self):
        self.shut = True

    async def start_polling(self, **kwargs):
        self.updated_polling = True

    @property
    def running(self):
        return self.started and not self.stopped


@pytest.fixture()
def fake_builder(monkeypatch, ready_db):
    from tuyabot.settings import service

    service.patch({"telegram.enabled": True}, actor={})
    FakeApplication.instances.clear()
    FakeApplication.fail_tokens.clear()

    def build(token: str) -> FakeApplication:
        app = FakeApplication(token)
        FakeApplication.instances.append(app)
        return app

    manager = manager_module.BotManager()
    monkeypatch.setattr(manager, "_build", build)
    return manager


def _create_bot(label: str, token: str) -> int:
    return bots_repo.create(label, token)


def test_two_bots_run_independently(fake_builder):
    first = _create_bot("produksi", "token-a")
    second = _create_bot("uji", "token-b")

    async def scenario():
        assert await fake_builder.enable(first) == "running"
        assert await fake_builder.enable(second) == "running"
        assert set(fake_builder.running_ids()) == {first, second}

        await fake_builder.disable(first)
        assert fake_builder.running_ids() == [second]

    asyncio.run(scenario())


def test_bad_token_does_not_stop_other_bots(fake_builder):
    good = _create_bot("baik", "token-good")
    bad = _create_bot("buruk", "token-bad")
    FakeApplication.fail_tokens.add("token-bad")

    async def scenario():
        await fake_builder.enable(good)
        assert await fake_builder.enable(bad) == "error"
        assert fake_builder.running_ids() == [good]

    asyncio.run(scenario())

    record = bots_repo.get(bad)
    assert "berjalan di tempat lain" in record["last_error"]


def test_rebuild_only_touches_that_bot(fake_builder):
    first = _create_bot("satu", "token-1")
    second = _create_bot("dua", "token-2")

    async def scenario():
        await fake_builder.enable(first)
        await fake_builder.enable(second)
        await fake_builder.rebuild(first)
        assert set(fake_builder.running_ids()) == {first, second}

    asyncio.run(scenario())
    assert bots_repo.get(first)["last_error"] is None


def test_duplicate_token_rejected(ready_db):
    bots_repo.create("a", "sama")
    with pytest.raises(bots_repo.BotError) as excinfo:
        bots_repo.create("b", "sama")
    assert excinfo.value.code == "token"


def test_token_is_never_listed(ready_db):
    bots_repo.create("rahasia", "123:abc")
    listed = bots_repo.list_all()
    assert "token" not in listed[0]
    assert "token_sha256" not in listed[0]


def test_api_lists_bots_without_tokens(client, login_as):
    login_as("superadmin")
    client.post("/api/bots", json={"label": "produksi", "token": "42:secret"})
    body = client.get("/api/bots").json()
    assert len(body["bots"]) == 1
    assert "secret" not in str(body)


def test_api_duplicate_token_is_409(client, login_as):
    login_as("superadmin")
    client.post("/api/bots", json={"label": "a", "token": "sama:token"})
    response = client.post("/api/bots", json={"label": "b", "token": "sama:token"})
    assert response.status_code == 409


def test_api_bot_create_needs_a_session(client):
    """Bots are reachable once authenticated; anonymous callers are refused."""
    assert client.post("/api/bots", json={"label": "x", "token": "y"}).status_code == 401


def test_invalid_token_is_redacted_from_last_error(fake_builder):
    """last_error is returned by GET /api/bots, so it must never contain the token."""
    token = "987654321:AAFakeSecretThatMustNotLeak"
    bot_id = _create_bot("bocor", token)
    FakeApplication.fail_tokens.discard(token)

    async def exploding_initialize(self):
        raise RuntimeError(f"The token `{token}` was rejected by the server.")

    FakeApplication.initialize = exploding_initialize
    try:
        asyncio.run(fake_builder.enable(bot_id))
    finally:
        del FakeApplication.initialize

    stored = bots_repo.get(bot_id)["last_error"]
    assert token not in stored
    assert "AAFakeSecretThatMustNotLeak" not in stored
    assert "[token]" in stored


def test_sanitize_removes_bare_id_prefix():
    from tuyabot.telegram.manager import _sanitize

    cleaned = _sanitize("error 987654321 happened", "987654321:secret")
    assert "987654321" not in cleaned


def test_api_never_returns_token_even_after_failure(client, login_as, ready_db):
    from tuyabot.storage.repos import bots as repo

    login_as("superadmin")
    token = "555444333:AABigSecretValue"
    bot_id = repo.create("gagal", token)
    repo.record_error(bot_id, "rejected `555444333:AABigSecretValue`")

    body = client.get("/api/bots").json()
    assert token not in str(body)
