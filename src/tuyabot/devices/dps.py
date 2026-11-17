"""Device address and DPS mapping.

A device row stores `dps` as a semantic → DP-index map, e.g.
    {"switch": 1, "power": 19, "current": 18, "voltage": 20}
No code may assume a particular device always uses DP 1/18/19/20 — the map
is what routes status, power logging, and control.
"""

from __future__ import annotations

from typing import Any

TEMPLATES: dict[str, dict[str, int]] = {
    "plug": {"switch": 1, "current": 18, "power": 19, "voltage": 20},
    "bulb": {"switch": 20, "brightness": 22, "temp": 23, "colour": 24},
    "switch": {"switch": 1},
    "sensor": {},
}

DEVICE_TYPES = tuple(TEMPLATES)
FEATURES = ("power_logging", "watchdog")

# Mapping from the semantic key in `dps` to the normalized output field.
_OUTPUT = {
    "switch": "switch_on",
    "power": "power_w",
    "current": "current_a",
    "voltage": "voltage_v",
    "brightness": "brightness",
    "temp": "colour_temp",
    "colour": "colour",
}


def template_for(device_type: str) -> dict[str, int]:
    return dict(TEMPLATES.get(device_type, {}))


def validate(dps: Any, device_type: str) -> dict[str, int]:
    """Normalize a DPS map: keys are semantic names, values are DP indices."""
    if dps is None:
        return {}
    if not isinstance(dps, dict):
        raise ValueError("dps harus objek")
    normalized: dict[str, int] = {}
    for key, value in dps.items():
        if key not in _OUTPUT:
            raise ValueError(f"kunci dps tidak dikenal: {key}")
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError(f"dps.{key} harus angka")
        if value < 0:
            raise ValueError(f"dps.{key} tidak boleh negatif")
        normalized[key] = value
    return normalized


def extract(device: dict[str, Any], raw: Any) -> dict[str, Any]:
    """Pull mapped values out of a raw DPS payload.

    Accepts either the raw map or its envelope ({"dps": {...}}). Only keys the
    device maps are returned, so an unmapped DP never leaks into an API
    response or a power log.
    """
    if isinstance(raw, dict) and "dps" in raw and isinstance(raw["dps"], dict):
        raw = raw["dps"]
    if not isinstance(raw, dict):
        return {}

    mapping = device.get("dps") or {}
    output: dict[str, Any] = {}
    for semantic, index in mapping.items():
        key = str(index)
        if key not in raw:
            continue
        value = raw[key]
        field = _OUTPUT.get(semantic)
        if field is None:
            continue
        if semantic == "switch":
            output[field] = bool(value)
        elif semantic in ("power", "current", "voltage", "brightness"):
            try:
                output[field] = float(value)
            except (TypeError, ValueError):
                continue
        else:
            output[field] = value
    return output


def switch_index(device: dict[str, Any]) -> int | None:
    return (device.get("dps") or {}).get("switch")


def supports_power(device: dict[str, Any]) -> bool:
    mapping = device.get("dps") or {}
    return "power" in mapping or "current" in mapping


def has_feature(device: dict[str, Any], feature: str) -> bool:
    return bool((device.get("features") or {}).get(feature))
