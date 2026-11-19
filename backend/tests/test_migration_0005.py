"""Migration 0005/0006 against a database built by the old schema.

The unit tests elsewhere run on a database migrated from scratch. This one
builds the pre-change schema first, then applies the new migrations, which is
the only way to know what an existing installation goes through.
"""

import sqlite3
from pathlib import Path

from tuyabot.storage import db, migrate

OLD_SCHEMA = Path(__file__).resolve().parent.parent / "src/tuyabot/storage/migrations"


def _build_old_database(target: Path) -> None:
    """Apply 0001..0004 only, then insert data as the old app would have."""
    conn = sqlite3.connect(target)
    try:
        for name in ("0001_init.sql", "0002_seed.sql", "0003_settings_seed.sql", "0004_setup_state.sql"):
            conn.executescript((OLD_SCHEMA / name).read_text(encoding="utf-8"))
        conn.execute(
            "INSERT INTO devices (name, label, tuya_id, local_key, type, access_roles) "
            "VALUES ('pompa', 'Pompa', 't1', 'k', 'plug', '[3]')"
        )
        conn.commit()
    finally:
        conn.close()


def test_old_permissions_become_bot_permissions(tmp_path):
    target = tmp_path / "old.db"
    _build_old_database(target)

    db.configure(str(target))
    migrate.apply()

    with db.connection() as cur:
        cur.execute("SELECT permissions FROM roles WHERE slug = 'operator'")
        operator = cur.fetchone()["permissions"]
        cur.execute("SELECT permissions FROM roles WHERE slug = 'superadmin'")
        superadmin = cur.fetchone()["permissions"]

    # devices.view -> monitoring, logs.view -> view_logs; control/scan/manage
    # are gone because device access is per device now.
    assert "monitoring" in operator
    assert "view_logs" in operator
    assert "devices.control" not in operator
    assert "manage_users" in superadmin
    assert "system.restore" not in superadmin


def test_access_roles_columns_are_backfilled(tmp_path):
    target = tmp_path / "old.db"
    _build_old_database(target)

    db.configure(str(target))
    migrate.apply()

    with db.connection() as cur:
        cur.execute("SELECT role_id, device_id, can_view, can_on, can_off FROM role_device_access")
        rows = [dict(row) for row in cur.fetchall()]

    assert rows == [
        {"role_id": 3, "device_id": 1, "can_view": 1, "can_on": 1, "can_off": 1}
    ]


def test_bot_messages_are_seeded(tmp_path):
    target = tmp_path / "old.db"
    _build_old_database(target)

    db.configure(str(target))
    migrate.apply()

    with db.connection() as cur:
        cur.execute("SELECT COUNT(*) AS n FROM bot_messages")
        count = cur.fetchone()["n"]

    assert count == 32
