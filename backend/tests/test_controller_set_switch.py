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
    """Stands in for a tinytuya device client.

    It mimics the real signature — set_status(on, switch=1) — so a caller that
    passes the arguments in the wrong order is caught here. The previous fake
    recorded whatever it received, which is why the inverted call
    set_status(index, on) passed every test while the pump never switched.
    """

    def __init__(self, reply):
        self.reply = reply
        self.calls: list[tuple[bool, int]] = []

    def set_status(self, on, switch=1, nowait=False):
        self.calls.append((on, switch))
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
    assert client.calls == [(True, 1)]


def test_a_null_ack_is_accepted_and_keeps_the_client(fake_entry):
    """A null ACK is accepted here, but it is not proof the relay moved: the
    caller verifies by reading the DP back. Forgetting the client at this stage
    would also rebuild the socket on every toggle."""
    client = fake_entry(None)

    result = controller_module.controller.set_switch(DEVICE, True)

    assert result["success"] is True
    assert result["ack"] == "null"
    assert client.calls == [(True, 1)]


def test_set_switch_honours_an_off_command(fake_entry):
    client = fake_entry({"dps": {"1": False}})

    result = controller_module.controller.set_switch(DEVICE, False)

    assert result["success"] is True
    assert client.calls == [(False, 1)]


def test_set_switch_without_a_switch_dp_never_calls_the_device(fake_entry):
    client = fake_entry({"dps": {}})

    result = controller_module.controller.set_switch({"id": 2, "name": "sensor", "dps": {}}, True)

    assert result["success"] is False
    assert "switch" in result["message"]
    assert client.calls == []


def test_the_value_is_sent_to_the_switch_dp_not_the_other_way_round(fake_entry):
    """Regression for the inverted arguments.

    tinytuya's signature is set_status(on, switch=1): value first, DP index
    second. The code called set_status(index, on), so a command for DP 1 was
    sent as DP "True". The device answered with a null ACK because the frame was
    well-formed, and nothing changed — the pump stayed off while every toggle
    reported success. The fake mirrors the real signature, so an inversion fails
    here instead of on the device.
    """
    client = fake_entry(None)

    controller_module.controller.set_switch({"id": 1, "name": "pompa", "dps": {"switch": 7}}, False)

    on_value, dp_index = client.calls[0]
    assert on_value is False, "first argument must be the on/off value"
    assert dp_index == 7, "second argument must be the DP index"
