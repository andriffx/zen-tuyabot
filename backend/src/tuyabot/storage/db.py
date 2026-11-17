"""SQLite access layer: one connection per thread, WAL, generation counter.

Why one connection per thread: `asyncio.to_thread` / executors use unpredictable
threads, and sqlite3 Connections must not be shared across threads. We never pass
`check_same_thread=False`.

Why a generation counter: a restore replaces the DB file under the process. Each
thread remembers the generation it opened with; on mismatch it closes and reopens,
picking up the new file (and a fresh WAL).
"""

from __future__ import annotations

import sqlite3
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

_path: str = ":memory:"
_busy_timeout_ms: int = 5000
_generation: int = 0
_local = threading.local()
_configure_lock = threading.Lock()

PRAGMAS = (
    "PRAGMA journal_mode=WAL",
    "PRAGMA synchronous=NORMAL",
    "PRAGMA foreign_keys=ON",
    "PRAGMA wal_autocheckpoint=1000",
)


def configure(path: str, busy_timeout_ms: int = 5000) -> None:
    """Point the layer at a database file and reset thread-local connections."""
    global _path, _busy_timeout_ms
    with _configure_lock:
        close_all()
        _path = path
        _busy_timeout_ms = busy_timeout_ms
        if path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)


def bump_generation() -> None:
    """Invalidate every thread's connection (called after a DB file swap)."""
    global _generation
    with _configure_lock:
        _generation += 1


def current_generation() -> int:
    return _generation


def path() -> str:
    return _path


def _open() -> sqlite3.Connection:
    conn = sqlite3.connect(_path, timeout=_busy_timeout_ms / 1000)
    for pragma in PRAGMAS:
        conn.execute(pragma)
    conn.execute(f"PRAGMA busy_timeout={_busy_timeout_ms}")
    conn.row_factory = sqlite3.Row
    conn.isolation_level = None  # explicit transactions
    return conn


def _thread_connection() -> sqlite3.Connection:
    state = getattr(_local, "state", None)
    if state is not None:
        conn, generation = state
        if generation == _generation:
            return conn
        try:
            conn.close()
        finally:
            _local.state = None
    conn = _open()
    _local.state = (conn, _generation)
    return conn


@contextmanager
def connection(immediate: bool = False) -> Iterator[sqlite3.Cursor]:
    """Yield a cursor inside a committed (or rolled-back) transaction.

    `immediate=True` uses BEGIN IMMEDIATE for read-then-write sequences so two
    writers cannot interleave and lose an update.

    Reentrant: a nested `connection()` on the same thread joins the outer
    transaction instead of issuing a second BEGIN (which SQLite rejects). Only
    the outermost block commits or rolls back.
    """
    conn = _thread_connection()
    depth = getattr(_local, "depth", 0)
    cursor = conn.cursor()

    if depth == 0:
        cursor.execute("BEGIN IMMEDIATE" if immediate else "BEGIN")
    _local.depth = depth + 1

    try:
        yield cursor
        if depth == 0:
            conn.commit()
    except Exception:
        if depth == 0:
            try:
                conn.rollback()
            except Exception:
                pass
        raise
    finally:
        _local.depth = depth
        cursor.close()


@contextmanager
def raw_connection() -> Iterator[sqlite3.Cursor]:
    """Cursor with no transaction wrapper.

    Required by statements SQLite refuses inside a transaction, notably
    `VACUUM INTO` for consistent online backups.
    """
    conn = _thread_connection()
    cursor = conn.cursor()
    try:
        yield cursor
    finally:
        cursor.close()


def close_all() -> None:
    """Close this thread's connection. Full shutdown calls it per thread via executor."""
    state = getattr(_local, "state", None)
    if state is not None:
        conn, _ = state
        try:
            conn.close()
        finally:
            _local.state = None


def restore_in_place(source_path: str | Path) -> None:
    """Replace the *contents* of the live database with `source_path`.

    Restoring by swapping files (`os.replace`) only works when every thread's
    connection is closed first. That is impossible here: sqlite3 objects refuse
    `close()` from a thread other than the one that created them, so the
    uvicorn worker pool, the scheduler and the Telegram bots would keep a handle
    on the WAL file. On Windows the unlink then fails with WinError 32, and on
    POSIX the rename would leave those threads reading the deleted inode.

    The SQLite backup API writes the source into the live file in place, which
    every already-open connection observes as ordinary new data. Any connection
    with a stale read transaction must refresh; callers bump the generation
    afterwards so each thread reopens on its next use.
    """
    source_path = str(source_path)
    destination = _thread_connection()
    source = sqlite3.connect(source_path, timeout=_busy_timeout_ms / 1000)
    try:
        source.backup(destination)
    finally:
        source.close()


def ping() -> bool:
    try:
        with connection() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        return True
    except Exception:
        return False
