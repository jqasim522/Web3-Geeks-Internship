"""
tests/failure/test_db_locked.py — SQLite "database is locked" failure injection.

# STATUS: OFFLINE-CODE (not run here — no lib/ in this environment)
# RUN: pytest tests/failure/test_db_locked.py -v
# EXPECTED: A locked/busy SQLite connection surfaces as a graceful error
#           through rag_lib, never an unhandled sqlite3.OperationalError
#           reaching the end user as a raw traceback.

ASSUMPTION FLAGGED: without lib/rag_lib.py present, we cannot see whether
it already wraps DB calls in try/except. These tests describe the REQUIRED
behavior and use a real locked SQLite file to force the failure, rather
than mocking, since "database is locked" is filesystem/lock-manager
behavior that a mock could get wrong.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'lib'))

import sqlite3
import threading
import time
import pytest


@pytest.fixture
def locked_conn(db_path):
    """Open a second connection and hold an exclusive write lock on it by
    starting (but not committing) a write transaction, so any other
    connection's write attempt raises 'database is locked'."""
    holder_conn = sqlite3.connect(db_path, timeout=0.1)
    holder_conn.execute("BEGIN EXCLUSIVE")
    try:
        yield
    finally:
        holder_conn.rollback()
        holder_conn.close()


def test_write_while_locked_raises_operational_error_directly(db_path, locked_conn):
    """Sanity check that our lock-holding fixture actually produces the
    condition we want to test against (belt-and-suspenders for the fixture
    itself, independent of rag_lib)."""
    conn2 = sqlite3.connect(db_path, timeout=0.1)
    with pytest.raises(sqlite3.OperationalError):
        conn2.execute("INSERT INTO properties (property_id) VALUES ('TEST-0000')")
    conn2.close()


def test_get_property_read_during_write_lock_still_works(db_path, locked_conn):
    """SQLite allows concurrent READS while one connection holds a write
    lock (WAL mode) or may raise 'database is locked' in the default
    rollback journal mode — either way, get_property must not crash with
    an unhandled exception; it should return a row, None, or raise a
    documented, caught error."""
    import rag_lib as r
    conn2 = sqlite3.connect(db_path, timeout=0.1)
    conn2.row_factory = sqlite3.Row
    try:
        result = r.get_property("LAH-0001", conn=conn2)
        assert result is None or isinstance(result, dict) or hasattr(result, "keys")
    except sqlite3.OperationalError:
        pytest.fail(
            "get_property let a raw sqlite3.OperationalError escape during a "
            "read against a locked database — it should catch and handle this."
        )
    finally:
        conn2.close()


def test_query_properties_during_lock_does_not_crash_hard(db_path, locked_conn):
    import rag_lib as r
    conn2 = sqlite3.connect(db_path, timeout=0.1)
    conn2.row_factory = sqlite3.Row
    try:
        result = r.query_properties(conn=conn2, city="Lahore", limit=5)
        assert isinstance(result, list)
    except sqlite3.OperationalError:
        pytest.fail("query_properties let a raw sqlite3.OperationalError escape.")
    finally:
        conn2.close()
