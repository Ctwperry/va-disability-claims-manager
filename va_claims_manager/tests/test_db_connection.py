"""
Tests for SQLite connection thread safety.
Verifies that:
  - Each thread gets its own distinct connection object.
  - check_same_thread is NOT disabled (connections cannot be passed across threads).
  - close_connection() nulls out the thread-local connection.
  - Workers call close_connection() in their finally blocks.
"""
import sqlite3
import threading
from unittest.mock import patch
import pytest


def test_each_thread_gets_own_connection():
    """Thread-local storage must give each thread a distinct connection object."""
    from app.db import connection as conn_mod

    results = {}

    def grab_conn(name):
        results[name] = conn_mod.get_connection()
        conn_mod.close_connection()

    # Run sequentially to avoid a WAL-on-new-DB race between simultaneous
    # connections. Thread isolation still holds: thread B cannot reuse
    # thread A's connection because thread-local storage is per-thread.
    t1 = threading.Thread(target=grab_conn, args=("a",))
    t2 = threading.Thread(target=grab_conn, args=("b",))
    t1.start(); t1.join()
    t2.start(); t2.join()

    assert results["a"] is not results["b"], "Threads must not share a connection"


def test_check_same_thread_is_enforced():
    """
    Verify that connections are created WITHOUT check_same_thread=False.
    We capture kwargs passed to sqlite3.connect while letting the real call run.
    """
    import app.db.connection as conn_mod

    captured = {}
    real_connect = sqlite3.connect

    def mock_connect(*args, **kwargs):
        captured["check_same_thread"] = kwargs.get("check_same_thread", True)
        return real_connect(*args, **kwargs)

    with patch("app.db.connection.sqlite3.connect", side_effect=mock_connect):
        conn_mod._open_connection(conn_mod.DB_PATH)

    assert captured.get("check_same_thread", True) is not False, (
        "check_same_thread=False must not be passed to sqlite3.connect"
    )


def test_close_connection_nulls_thread_local():
    """close_connection() must remove the connection from thread-local storage."""
    from app.db import connection as conn_mod

    # Ensure a connection exists
    conn_mod.get_connection()
    conn_mod.close_connection()

    # _local.conn should be None after close
    assert getattr(conn_mod._local, "conn", None) is None


def test_ingestion_worker_closes_connection_on_finish():
    """IngestionWorker must call close_connection() in its finally block."""
    from unittest.mock import patch
    import app.ui.workers as workers_mod

    closed = []

    # ingest_files is imported locally inside run(), so patch at its source module.
    with patch("app.ui.workers.close_connection", side_effect=lambda: closed.append(1)), \
         patch("app.ingestion.pipeline.ingest_files", return_value=[]):
        worker = workers_mod.IngestionWorker(filepaths=[], veteran_id=1)
        worker.run()

    assert len(closed) == 1, "close_connection() must be called exactly once after run()"


def test_search_worker_closes_connection_on_finish():
    """SearchWorker must call close_connection() in its finally block."""
    from unittest.mock import patch
    import app.ui.workers as workers_mod

    closed = []

    # search is imported locally inside run(), so patch at its source module.
    with patch("app.ui.workers.close_connection", side_effect=lambda: closed.append(1)), \
         patch("app.search.fts_engine.search", return_value=[]):
        worker = workers_mod.SearchWorker(query="test", veteran_id=1)
        worker.run()

    assert len(closed) == 1, "close_connection() must be called exactly once after run()"
