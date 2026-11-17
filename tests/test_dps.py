"""DPS mapping: templates, validation, extraction."""

import pytest

from tuyabot.devices import dps


def test_templates_cover_every_type():
    assert set(dps.TEMPLATES) == set(dps.DEVICE_TYPES)
    assert dps.template_for("plug") == {"switch": 1, "current": 18, "power": 19, "voltage": 20}
    assert dps.TEMPLATES["bulb"]["switch"] == 20


def test_extract_maps_only_declared_keys():
    device = {"dps": {"switch": 1, "power": 19}}
    raw = {"1": True, "19": 12.5, "99": "tidak dipetakan"}
    assert dps.extract(device, raw) == {"switch_on": True, "power_w": 12.5}


def test_extract_accepts_envelope():
    device = {"dps": {"switch": 20}}
    assert dps.extract(device, {"dps": {"20": False}}) == {"switch_on": False}


def test_extract_with_different_indices():
    """No code may assume DP 1/18/19/20 — the map decides."""
    device = {"dps": {"switch": 101, "power": 7}}
    assert dps.extract(device, {"101": True, "7": 3}) == {"switch_on": True, "power_w": 3.0}


def test_extract_ignores_missing_and_bad_values():
    device = {"dps": {"switch": 1, "power": 19}}
    assert dps.extract(device, {"power": "bukan angka"}) == {}


def test_extract_on_garbage_raw():
    device = {"dps": {"switch": 1}}
    assert dps.extract(device, None) == {}
    assert dps.extract(device, "teks") == {}


def test_validate_rejects_unknown_key_and_bad_types():
    with pytest.raises(ValueError):
        dps.validate({"tidak_ada": 1}, "plug")
    with pytest.raises(ValueError):
        dps.validate({"switch": "1"}, "plug")
    with pytest.raises(ValueError):
        dps.validate({"switch": True}, "plug")
    with pytest.raises(ValueError):
        dps.validate({"switch": -1}, "plug")


def test_switch_index_and_power_support():
    plug = {"dps": {"switch": 1, "power": 19}}
    sensor = {"dps": {}}
    assert dps.switch_index(plug) == 1
    assert dps.supports_power(plug) is True
    assert dps.supports_power(sensor) is False
    assert dps.switch_index(sensor) is None
