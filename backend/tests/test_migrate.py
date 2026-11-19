"""Migration runner: fresh apply, checksum guard, newer-DB refusal."""

import shutil
import sqlite3

import pytest

from tuyabot.storage import db, migrate


def _latest_version() -> int:
    return migrate.available()[-1][0]


def test_fresh_db_applies_all(fresh_db):
    assert migrate.apply() == _latest_version()
    with db.connection() as cur:
        cur.execute("SELECT count(*) FROM schema_migrations")
        assert cur.fetchone()[0] == len(migrate.available())
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='devices'")
        assert cur.fetchone() is not None


def test_applying_twice_is_idempotent(fresh_db):
    assert migrate.apply() == _latest_version()
    assert migrate.apply() == _latest_version()


def test_edited_migration_fails(fresh_db, tmp_path, monkeypatch):
    assert migrate.apply() == _latest_version()

    tampered = tmp_path / "migrations"
    tampered.mkdir()
    for _, _, path in migrate.available():
        shutil.copy(path, tampered / path.name)
    edited = tampered / "0001_init.sql"
    edited.write_text(edited.read_text(encoding="utf-8") + "\n-- edited\n", encoding="utf-8")

    monkeypatch.setattr(migrate, "MIGRATIONS_DIR", tampered)

    with pytest.raises(migrate.MigrationError, match="checksum"):
        migrate.apply()


def test_newer_db_refused(fresh_db):
    assert migrate.apply() == _latest_version()
    with db.connection() as cur:
        cur.execute(
            "INSERT INTO schema_migrations (version, name, checksum) VALUES (99, 'from_the_future', 'x')"
        )
    with pytest.raises(migrate.MigrationError, match="lebih baru"):
        migrate.apply()


def test_missing_migration_file_fails(fresh_db, tmp_path, monkeypatch):
    assert migrate.apply() == _latest_version()
    empty = tmp_path / "migrations"
    empty.mkdir()
    (empty / "0001_init.sql").write_text("SELECT 1;", encoding="utf-8")
    monkeypatch.setattr(migrate, "MIGRATIONS_DIR", empty)
    with pytest.raises(migrate.MigrationError):
        migrate.apply()


def test_failed_migration_is_rolled_back_entirely(fresh_db, tmp_path, monkeypatch):
    """A migration that fails halfway must leave no partial schema behind.

    executescript() implicitly commits, so this guards against that regression:
    after a failure, neither the migration's objects nor its versions row exist.
    """
    assert migrate.apply() == _latest_version()
    applied_version = _latest_version()  # captured before the broken dir is patched in
    with db.connection() as cur:
        cur.execute("SELECT name FROM sqlite_master")
        before = {row[0] for row in cur.fetchall()}

    broken_dir = tmp_path / "migrations"
    shutil.copytree(migrate.MIGRATIONS_DIR, broken_dir)
    # Must be the next free version. Hardcoding a number breaks as soon as a real
    # migration takes it: the fixture then writes a duplicate version that the
    # runner never executes, and this test silently stops testing rollback.
    (broken_dir / f"{applied_version + 1:04d}_broken.sql").write_text(
        "CREATE TABLE should_not_exist (x INTEGER);\n"
        "THIS IS NOT VALID SQL;\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(migrate, "MIGRATIONS_DIR", broken_dir)

    with pytest.raises(sqlite3.OperationalError):
        migrate.apply()

    with db.connection() as cur:
        cur.execute("SELECT name FROM sqlite_master WHERE name = 'should_not_exist'")
        assert cur.fetchone() is None
        cur.execute("SELECT MAX(version) FROM schema_migrations")
        assert cur.fetchone()[0] == applied_version
    assert before  # sanity: the pre-state was readable


def test_split_statements_keeps_multiline_create_table_together():
    statements = migrate._split_statements(
        "CREATE TABLE a (\n  x INTEGER,\n  y TEXT\n);\nCREATE INDEX i ON a(x);\n"
    )
    assert len(statements) == 2
    assert statements[0].startswith("CREATE TABLE a")
    assert statements[0].endswith(");")


def test_a_migration_that_shipped_in_several_forms_still_starts(tmp_path):
    """0006 was edited six times before its content settled.

    A database that applied an earlier form recorded a checksum that no longer
    matches the file. Refusing to start there locks a live installation out
    because of a mistake in how the migration was maintained, not because its
    data is wrong.
    """
    recorded = "ddcae867c0069a9902ba839b01da1aad449ed2af1d735fd9a87ac68a6d7a767b"
    assert migrate._matches_applied(
        6, "0006_bot_messages_seed", migrate.MIGRATIONS_DIR / "0006_bot_messages_seed.sql", recorded
    )


def test_tolerance_is_limited_to_the_named_migration(tmp_path):
    """Any checksum is accepted for 0006 only; every other file is enforced.

    0006 shipped in six forms, all of which insert the same core rows and are
    reconciled by 0007. No other migration has that history, so an unknown
    checksum there still means someone edited a released file.
    """
    path = tmp_path / "9999_other.sql"
    path.write_bytes(b"SELECT 1;\n")

    assert not migrate._matches_applied(9999, "9999_other", path, "0" * 64)
    assert migrate._matches_applied(6, "0006_bot_messages_seed", path, "0" * 64)


def test_a_database_that_applied_an_old_0006_starts_and_gets_the_new_rows(tmp_path):
    """The exact production failure: an old 0006 checksum on record.

    The server applied an earlier form of 0006 and refused to start after the
    update. The old checksum must be accepted, and 0007 must still add the rows
    that were added later.
    """

    import sqlite3

    target = tmp_path / "old.db"
    # Build the real schema first, then rewrite 0006's checksum to an old value.
    conn = sqlite3.connect(target)
    try:
        for name in ("0001_init.sql", "0002_seed.sql", "0003_settings_seed.sql",
                     "0004_setup_state.sql", "0005_telegram_roles.sql"):
            conn.executescript((migrate.MIGRATIONS_DIR / name).read_text(encoding="utf-8"))
        conn.execute(
            "INSERT INTO schema_migrations (version, name, checksum) VALUES (6, ?, ?)",
            (
                "0006_bot_messages_seed",
                "ddcae867c0069a9902ba839b01da1aad449ed2af1d735fd9a87ac68a6d7a767b",
            ),
        )
        for version, name, path in migrate.available():
            if version < 6:
                conn.execute(
                    "INSERT OR IGNORE INTO schema_migrations (version, name, checksum) VALUES (?, ?, ?)",
                    (version, name, migrate._checksum(path)),
                )
        conn.commit()
    finally:
        conn.close()
    migrate.db.configure(str(target))

    # Must not raise.
    assert migrate.apply() >= 7
    with migrate.db.connection() as cur:
        cur.execute("SELECT COUNT(*) AS n FROM bot_messages")
        assert cur.fetchone()["n"] > 0
