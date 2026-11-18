"""set_switch must always return the dict shape its callers expect.

tinytuya's set_status returns the raw reply, which is None when the device does
not answer. The previous implementation passed that straight through, so
`result.get("success")` in the route raised

    AttributeError: 'NoneType' object has no attribute 'get'

and the dashboard got a 500 when the user tried to switch a device on. Every
caller (web route, Telegram handler, watchdog) reads `result["success"]`, so the
contract is fixed here rather than at each call site.
"""

from __future__ import annotations

import pytest

from tuyabot.devices import controller as controller_module


class FakeClient:
    """Stands in for a tinytuya device client; records what it was asked."""

    def __init__(self, reply):
        self.reply = reply
        self.calls: list[tuple] = []

    def set_status(self, index, on):
        self.calls.append((index, on))
        return self.reply


@pytest.fixture()
def fake_entry(monkeypatch):
    """Bypass the real client: _call resolves entries through controller._entry."""
    holder: dict[str, FakeClient] = {}

    def make(reply):
        client = FakeClient(reply)
        holder["client"] = client
        monkeypatch.setattr(
            controller_module.controller,
            "_entry",
            lambda device: {"client": client, "lock": __import__("threading").Lock()},
        )
        return client

    return make


DEVICE = {"id": 1, "name": "pompa", "dps": {"switch": 1}}


@pytest.mark.parametrize(
    ("reply", "expected_success", "message_contains"),
    [
        # A null ACK is how Tuya confirms a control command. tinytuya returns
        # None for it, so None means success — the opposite of a network error.
        (None, True, ""),
        ({"Error": "Network Error"}, False, "Network Error"),
        ("bukan dict", False, "tak dikenal"),
        ({"devId": "x", "dps": {"1": True}}, True, ""),
    ],
)
def test_set_switch_normalises_every_reply_shape(fake_entry, reply, expected_success, message_contains):
    client = fake_entry(reply)

    result = controller_module.controller.set_switch(DEVICE, True)

    assert isinstance(result, dict), f"callers expect a dict, got {type(result)}"
    assert result["success"] is expected_success
    if message_contains:
        assert message_contains in result["message"]
    assert client.calls == [(1, True)]


def test_a_null_ack_counts_as_success_and_keeps_the_client(fake_entry):
    """Forgetting the client on a successful command would rebuild a socket
    on every toggle; that only belongs on a real failure."""
    client = fake_entry(None)

    result = controller_module.controller.set_switch(DEVICE, True)

    assert result == {"success": True}
    assert client.calls == [(1, True)]


def test_set_switch_honours_an_off_command(fake_entry):
    client = fake_entry({"dps": {"1": False}})

    result = controller_module.controller.set_switch(DEVICE, False)

    assert result["success"] is True
    assert client.calls == [(1, False)]


def test_set_switch_without_a_switch_dp_never_calls_the_device(fake_entry):
    client = fake_entry({"dps": {}})

    result = controller_module.controller.set_switch({"id": 2, "name": "sensor", "dps": {}}, True)

    assert result["success"] is False
    assert "switch" in result["message"]
    assert client.calls == []
