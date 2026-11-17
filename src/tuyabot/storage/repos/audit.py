"""Audit log — who changed what, when, from where, and whether it succeeded.

Audit rows are written in the same transaction as the change where possible.
For denials (`403`) the write happens after the fact and must never break the
request; a failure is surfaced in app_error_logs instead of being swallowed.
"""

from __future__ import annotations

import json
import logging
import traceback
from typing import Any

from .. import db

logger = logging.getLogger(__name__)


def write(
    actor_kind: str,
    actor_id: int | None,
    actor_label: str | None,
    action: str,
    *,
    target_kind: str | None = None,
    target_id: Any = None,
    result: str = "ok",
    ip: str | None = None,
    details: dict[str, Any] | None = None,
    request_id: str | None = None,
) -> None:
    """Record an audit entry. Never raises."""
    try:
        with db.connection(immediate=True) as cur:
            cur.execute(
                """
                INSERT INTO audit_logs
                    (actor_kind, actor_id, actor_label, action, target_kind,
                     target_id, result, ip, details, request_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    actor_kind,
                    actor_id,
                    actor_label,
                    action,
                    target_kind,
                    str(target_id) if target_id is not None else None,
                    result,
                    ip,
                    json.dumps(details, default=str) if details is not None else None,
                    request_id,
                ),
            )
    except Exception as exc:
        logger.error("[AUDIT] Gagal menulis audit %s: %s", action, exc)
        _record_failure(action, exc)


def _record_failure(action: str, exc: BaseException) -> None:
    """Surface a lost audit row in app_error_logs — a missing audit must be visible."""
    try:
        with db.connection(immediate=True) as cur:
            cur.execute(
                """
                INSERT INTO app_error_logs
                    (level, logger_name, message, exception_trace, file_name, line_number)
                VALUES ('ERROR', 'tuyabot.audit', ?, ?, 'audit.py', 0)
                """,
                (f"audit write failed for {action}", traceback.format_exc()),
            )
    except Exception:
        logger.exception("[AUDIT] Juga gagal mencatat kegagalan audit")


def list_page(
    *,
    limit: int = 50,
    offset: int = 0,
    actor_kind: str | None = None,
    action: str | None = None,
    result: str | None = None,
    target_kind: str | None = None,
    request_id: str | None = None,
    since: str | None = None,
    until: str | None = None,
) -> list[dict[str, Any]]:
    clauses: list[str] = []
    params: list[Any] = []
    for column, value in (
        ("actor_kind", actor_kind),
        ("action", action),
        ("result", result),
        ("target_kind", target_kind),
        ("request_id", request_id),
    ):
        if value:
            clauses.append(f"{column} = ?")
            params.append(value)
    if since:
        clauses.append("at >= ?")
        params.append(since)
    if until:
        clauses.append("at <= ?")
        params.append(until)
    where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
    params.extend([max(1, min(limit, 200)), max(0, offset)])

    with db.connection() as cur:
        cur.execute(f"SELECT * FROM audit_logs{where} ORDER BY at DESC, id DESC LIMIT ? OFFSET ?", params)
        rows = []
        for row in cur.fetchall():
            data = dict(row)
            if data.get("details"):
                try:
                    data["details"] = json.loads(data["details"])
                except ValueError:
                    pass
            rows.append(data)
        return rows


def prune(retention_days: int) -> int:
    with db.connection(immediate=True) as cur:
        cur.execute(
            "DELETE FROM audit_logs WHERE at < datetime('now','localtime', ?)",
            (f"-{int(retention_days)} days",),
        )
        return cur.rowcount
