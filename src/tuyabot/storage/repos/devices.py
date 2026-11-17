"""Device repository."""

from __future__ import annotations

import json
from typing import Any

from ...devices import dps as dps_module
from .. import db


class DeviceError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def _row_to_device(row) -> dict[str, Any]:
    device = dict(row)
    device["dps"] = json.loads(device.get("dps") or "{}")
    device["features"] = json.loads(device.get("features") or "{}")
    device["access_roles"] = json.loads(device.get("access_roles") or "[]")
    device["is_active"] = bool(device.get("is_active"))
    return device


def list_all(*, active_only: bool = False) -> list[dict[str, Any]]:
    query = "SELECT * FROM devices"
    if active_only:
        query += " WHERE is_active = 1"
    query += " ORDER BY sort_order, label, id"
    with db.connection() as cur:
        cur.execute(query)
        return [_row_to_device(row) for row in cur.fetchall()]


def get(device_id: int) -> dict[str, Any] | None:
    with db.connection() as cur:
        cur.execute("SELECT * FROM devices WHERE id = ?", (device_id,))
        row = cur.fetchone()
        return _row_to_device(row) if row else None


def get_by_name(name: str) -> dict[str, Any] | None:
    with db.connection() as cur:
        cur.execute("SELECT * FROM devices WHERE name = ?", (name,))
        row = cur.fetchone()
        return _row_to_device(row) if row else None


def create(payload: dict[str, Any]) -> int:
    name = str(payload.get("name", "")).strip().lower()
    if not name or not name.replace("-", "").replace("_", "").isalnum():
        raise DeviceError("name", "nama perangkat wajib (huruf, angka, - atau _)")
    device_type = str(payload.get("type") or "plug")
    if device_type not in dps_module.DEVICE_TYPES:
        raise DeviceError("type", f"tipe harus salah satu: {', '.join(dps_module.DEVICE_TYPES)}")

    mapping = payload.get("dps")
    if mapping is None:
        mapping = dps_module.template_for(device_type)
    try:
        mapping = dps_module.validate(mapping, device_type)
    except ValueError as exc:
        raise DeviceError("dps", str(exc)) from exc

    features = payload.get("features") or {}
    if not isinstance(features, dict):
        raise DeviceError("features", "features harus objek")

    access_roles = payload.get("access_roles") or []
    if not isinstance(access_roles, list) or not all(isinstance(x, int) for x in access_roles):
        raise DeviceError("access_roles", "access_roles harus array id role")

    try:
        with db.connection(immediate=True) as cur:
            cur.execute(
                """
                INSERT INTO devices
                    (name, label, tuya_id, local_key, ip, version, type, dps,
                     features, access_roles, is_active, sort_order)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    name,
                    str(payload.get("label") or name),
                    str(payload.get("tuya_id", "")),
                    str(payload.get("local_key", "")),
                    payload.get("ip"),
                    float(payload.get("version") or 3.5),
                    device_type,
                    json.dumps(mapping),
                    json.dumps(features),
                    json.dumps(sorted(access_roles)),
                    1 if payload.get("is_active", True) else 0,
                    int(payload.get("sort_order") or 0),
                ),
            )
            return int(cur.lastrowid)
    except Exception as exc:
        message = str(exc)
        if "devices.name" in message:
            raise DeviceError("name", "nama perangkat sudah dipakai") from exc
        if "devices.tuya_id" in message:
            raise DeviceError("tuya_id", "tuya_id sudah dipakai") from exc
        raise


_FIELD_TO_COLUMN = {
    "name": "name",
    "label": "label",
    "ip": "ip",
    "local_key": "local_key",
    "version": "version",
    "type": "type",
    "is_active": "is_active",
    "sort_order": "sort_order",
}


def _throw(condition: bool, code: str, message: str) -> None:
    if condition:
        raise DeviceError(code, message)


def update(device_id: int, payload: dict[str, Any]) -> None:
    current = get(device_id)
    if current is None:
        raise DeviceError("id", "perangkat tidak ditemukan")

    fields: dict[str, Any] = {}
    for key, column in _FIELD_TO_COLUMN.items():
        if key not in payload:
            continue
        value = payload[key]
        if key == "is_active":
            value = 1 if value else 0
        elif key == "version":
            value = float(value)
        elif key == "sort_order":
            value = int(value)
        elif key in ("name", "type"):
            value = str(value).strip().lower()
        else:
            value = str(value)
        fields[column] = value

    if "type" in payload:
        _throw(fields["type"] not in dps_module.DEVICE_TYPES, "type", "tipe perangkat tidak dikenal")

    if "dps" in payload:
        try:
            fields["dps"] = json.dumps(dps_module.validate(payload["dps"], current["type"]))
        except ValueError as exc:
            raise DeviceError("dps", str(exc)) from exc

    if "features" in payload:
        features = payload["features"]
        _throw(not isinstance(features, dict), "features", "features harus objek")
        fields["features"] = json.dumps(features)

    if "access_roles" in payload:
        roles = payload["access_roles"]
        _throw(
            not isinstance(roles, list) or not all(isinstance(x, int) for x in roles),
            "access_roles",
            "access_roles harus array id role",
        )
        fields["access_roles"] = json.dumps(sorted(roles))

    if not fields:
        return

    assignments = ", ".join(f"{column} = ?" for column in fields)
    values = [*fields.values(), device_id]
    try:
        with db.connection(immediate=True) as cur:
            cur.execute(
                f"UPDATE devices SET {assignments}, updated_at = datetime('now','localtime') WHERE id = ?",
                values,
            )
    except Exception as exc:
        message = str(exc)
        if "devices.name" in message:
            raise DeviceError("name", "nama perangkat sudah dipakai") from exc
        if "devices.tuya_id" in message:
            raise DeviceError("tuya_id", "tuya_id sudah dipakai") from exc
        raise


def delete(device_id: int) -> None:
    with db.connection(immediate=True) as cur:
        cur.execute("DELETE FROM devices WHERE id = ?", (device_id,))


def mark_seen(device_id: int, error: str | None = None) -> None:
    with db.connection(immediate=True) as cur:
        if error:
            cur.execute(
                "UPDATE devices SET last_error = ? WHERE id = ?",
                (error[:500], device_id),
            )
        else:
            cur.execute(
                "UPDATE devices SET last_seen_at = datetime('now','localtime'), last_error = NULL WHERE id = ?",
                (device_id,),
            )


def get_setting(device_id: int, key: str, default: Any = None) -> Any:
    with db.connection() as cur:
        cur.execute("SELECT value FROM device_settings WHERE device_id = ? AND key = ?", (device_id, key))
        row = cur.fetchone()
    if row is None:
        return default
    try:
        return json.loads(row["value"])
    except ValueError:
        return default


def set_setting(device_id: int, key: str, value: Any) -> None:
    with db.connection(immediate=True) as cur:
        cur.execute(
            "INSERT INTO device_settings (device_id, key, value) VALUES (?, ?, ?) "
            "ON CONFLICT(device_id, key) DO UPDATE SET value = excluded.value",
            (device_id, key, json.dumps(value)),
        )
