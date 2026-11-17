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
    (broken_dir / "0005_broken.sql").write_text(
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
