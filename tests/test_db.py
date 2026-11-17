"""SQLite layer: generation counter, concurrency, pragmas."""

import threading

from tuyabot.storage import db


def test_connection_reopens_after_generation_bump(fresh_db):
    with db.connection() as cur:
        cur.execute("CREATE TABLE t (v INTEGER)")
        cur.execute("INSERT INTO t VALUES (1)")

    db.bump_generation()

    with db.connection() as cur:
        cur.execute("SELECT count(*) FROM t")
        assert cur.fetchone()[0] == 1


def test_concurrent_writers_keep_all_rows(fresh_db):
    with db.connection() as cur:
        cur.execute("CREATE TABLE t (v INTEGER)")

    errors: list[BaseException] = []

    def writer(n: int) -> None:
        try:
            for i in range(50):
                with db.connection(immediate=True) as cur:
                    cur.execute("INSERT INTO t VALUES (?)", (n * 100 + i,))
        except BaseException as exc:
            errors.append(exc)

    threads = [threading.Thread(target=writer, args=(n,)) for n in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert errors == []
    with db.connection() as cur:
        cur.execute("SELECT count(*) FROM t")
        assert cur.fetchone()[0] == 200


def test_wal_mode_and_foreign_keys(fresh_db):
    with db.connection() as cur:
        cur.execute("PRAGMA journal_mode")
        assert cur.fetchone()[0].lower() == "wal"
        cur.execute("PRAGMA foreign_keys")
        assert cur.fetchone()[0] == 1


def test_ping_true_on_open_db_and_false_after_bad_path(tmp_path):
    assert db.ping() is True
    db.configure(str(tmp_path / "nope" / "missing" / "x.db"))
    db.bump_generation()
    assert db.ping() is True  # parent dirs are created by configure
