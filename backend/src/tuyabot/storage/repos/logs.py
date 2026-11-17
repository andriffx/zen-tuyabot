"""Activity and power log repository."""

from __future__ import annotations

from typing import Any

from .. import db


def log_activity(
    *,
    device_id: int | None,
    user_id: int | None,
    actor: str,
    action: str,
    status: str,
    message: str | None = None,
    bot_id: int | None = None,
) -> None:
    with db.connection(immediate=True) as cur:
        cur.execute(
            """
            INSERT INTO device_activity_logs
                (device_id, user_id, actor, bot_id, action, status, message)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (device_id, user_id, actor, bot_id, action, status, (message or "")[:1000]),
        )


def log_power(
    *,
    device_id: int,
    power_w: float,
    voltage_v: float,
    current_a: float,
    switch_state: bool | None,
    source: str,
) -> None:
    with db.connection(immediate=True) as cur:
        cur.execute(
            """
            INSERT INTO device_power_logs
                (device_id, power_w, voltage_v, current_a, switch_state, source)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                device_id,
                float(power_w),
                float(voltage_v),
                float(current_a),
                None if switch_state is None else (1 if switch_state else 0),
                source,
            ),
        )


def recent_activities(
    *, limit: int = 50, offset: int = 0, device_id: int | None = None
) -> list[dict[str, Any]]:
    query = """
        SELECT a.*, d.name AS device_name, d.label AS device_label
        FROM device_activity_logs a
        LEFT JOIN devices d ON d.id = a.device_id
    """
    params: list[Any] = []
    if device_id is not None:
        query += " WHERE a.device_id = ?"
        params.append(device_id)
    query += " ORDER BY a.created_at DESC, a.id DESC LIMIT ? OFFSET ?"
    params.extend([max(1, min(limit, 200)), max(0, offset)])

    with db.connection() as cur:
        cur.execute(query, params)
        return [dict(row) for row in cur.fetchall()]


def recent_power(*, limit: int = 50, offset: int = 0, device_id: int | None = None) -> list[dict[str, Any]]:
    query = """
        SELECT p.*, d.name AS device_name, d.label AS device_label
        FROM device_power_logs p
        LEFT JOIN devices d ON d.id = p.device_id
    """
    params: list[Any] = []
    if device_id is not None:
        query += " WHERE p.device_id = ?"
        params.append(device_id)
    query += " ORDER BY p.created_at DESC, p.id DESC LIMIT ? OFFSET ?"
    params.extend([max(1, min(limit, 200)), max(0, offset)])

    with db.connection() as cur:
        cur.execute(query, params)
        return [dict(row) for row in cur.fetchall()]


def recent_errors(*, limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
    with db.connection() as cur:
        cur.execute(
            "SELECT * FROM app_error_logs ORDER BY created_at DESC, id DESC LIMIT ? OFFSET ?",
            (max(1, min(limit, 200)), max(0, offset)),
        )
        return [dict(row) for row in cur.fetchall()]


def log_app_error(
    *,
    level: str,
    logger_name: str,
    message: str,
    trace: str | None = None,
    file_name: str | None = None,
    line_number: int | None = None,
) -> None:
    with db.connection(immediate=True) as cur:
        cur.execute(
            """
            INSERT INTO app_error_logs
                (level, logger_name, message, exception_trace, file_name, line_number)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (level, logger_name, message[:2000], trace, file_name, line_number),
        )


def cleanup(retention_days: int, audit_retention_days: int) -> dict[str, int]:
    """Housekeeping: drop old telemetry and audit rows. Returns per-table counts."""
    removed: dict[str, int] = {}
    table_specs = (
        ("device_activity_logs", "created_at", retention_days),
        ("device_power_logs", "created_at", retention_days),
        ("app_error_logs", "created_at", retention_days),
        ("audit_logs", "at", audit_retention_days),
    )
    with db.connection(immediate=True) as cur:
        for table, column, days in table_specs:
            cur.execute(
                f"DELETE FROM {table} WHERE {column} < datetime('now','localtime', ?)",
                (f"-{int(days)} days",),
            )
            removed[table] = cur.rowcount
    return removed


def count_rows() -> dict[str, int]:
    tables = (
        "devices",
        "web_users",
        "telegram_users",
        "device_activity_logs",
        "device_power_logs",
        "app_error_logs",
        "audit_logs",
        "backup_runs",
    )
    with db.connection() as cur:
        counts: dict[str, int] = {}
        for table in tables:
            cur.execute(f"SELECT COUNT(*) FROM {table}")
            counts[table] = int(cur.fetchone()[0])
        return counts
