"""Migration runner: fresh apply, checksum guard, newer-DB refusal."""

import pytest

from tuyabot.storage import db, migrate


def test_fresh_db_applies_all(fresh_db):
    assert migrate.apply() == 1
    with db.connection() as cur:
        cur.execute("SELECT count(*) FROM schema_migrations")
        assert cur.fetchone()[0] == 1
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='devices'")
        assert cur.fetchone() is not None


def test_applying_twice_is_idempotent(fresh_db):
    assert migrate.apply() == 1
    assert migrate.apply() == 1


def test_edited_migration_fails(fresh_db, tmp_path, monkeypatch):
    assert migrate.apply() == 1

    tampered = tmp_path / "migrations"
    tampered.mkdir()
    source = migrate.MIGRATIONS_DIR / "0001_init.sql"
    (tampered / "0001_init.sql").write_text(source.read_text() + "\n-- edited\n", encoding="utf-8")
    monkeypatch.setattr(migrate, "MIGRATIONS_DIR", tampered)

    with pytest.raises(migrate.MigrationError):
        migrate.apply()


def test_newer_db_refused(fresh_db):
    assert migrate.apply() == 1
    with db.connection() as cur:
        cur.execute(
            "INSERT INTO schema_migrations (version, name, checksum) VALUES (99, 'from_the_future', 'x')"
        )
    with pytest.raises(migrate.MigrationError):
        migrate.apply()


def test_missing_migration_file_fails(fresh_db, tmp_path, monkeypatch):
    assert migrate.apply() == 1
    empty = tmp_path / "migrations"
    empty.mkdir()
    (empty / "0001_init.sql").write_text("SELECT 1;", encoding="utf-8")
    monkeypatch.setattr(migrate, "MIGRATIONS_DIR", empty)
    with pytest.raises(migrate.MigrationError):
        migrate.apply()
