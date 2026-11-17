"""Audit log writing, filtering, and failure surfacing."""

import pytest

from tuyabot.storage import db, migrate
from tuyabot.storage.repos import audit


@pytest.fixture()
def ready(fresh_db):
    migrate.apply()
    return fresh_db


def test_audit_row_written_with_details_json(ready):
    audit.write("system", None, "startup", "system.start", details={"schema": 2})

    rows = audit.list_page()
    assert len(rows) == 1
    assert rows[0]["action"] == "system.start"
    assert rows[0]["details"] == {"schema": 2}
    assert rows[0]["result"] == "ok"


def test_filters_and_pagination(ready):
    for index in range(5):
        audit.write(
            "web",
            1,
            "root",
            "settings.patch",
            target_kind="settings",
            target_id=f"key{index}",
            result="ok" if index % 2 == 0 else "denied",
        )

    assert len(audit.list_page(result="denied")) == 2
    assert len(audit.list_page(action="settings.patch", limit=2)) == 2
    assert audit.list_page(limit=2, offset=4)[0]["target_id"] == "key0"


def test_failure_is_recorded_in_app_error_logs(ready, monkeypatch):
    """A failed audit write must be visible in app_error_logs, not swallowed."""

    def boom(*args, **kwargs):
        raise TypeError("details tidak bisa diserialisasi")

    monkeypatch.setattr(audit.json, "dumps", boom)
    audit.write("web", 1, "root", "users.create", details={"x": object()})

    monkeypatch.undo()
    with db.connection() as cur:
        cur.execute("SELECT level, message FROM app_error_logs")
        level, message = cur.fetchone()
    assert level == "ERROR"
    assert "audit write failed for users.create" in message


def test_prune_removes_old_rows(ready):
    with db.connection(immediate=True) as cur:
        cur.execute(
            "INSERT INTO audit_logs (at, actor_kind, action) "
            "VALUES (datetime('now','localtime','-400 days'), 'system', 'old.action')"
        )
    audit.write("system", None, None, "new.action")

    assert audit.prune(180) == 1
    actions = [row["action"] for row in audit.list_page()]
    assert actions == ["new.action"]
