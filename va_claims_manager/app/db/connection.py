"""
SQLite database connection management.
- WAL mode for non-blocking reads during document ingestion
- Foreign key enforcement
- Thread-local connections for PyQt worker threads
"""
import sqlite3
import threading
from pathlib import Path

from app.config import DB_PATH

_local = threading.local()


def get_connection() -> sqlite3.Connection:
    """Return a thread-local SQLite connection, creating it if needed."""
    conn = getattr(_local, "conn", None)
    if conn is None:
        conn = _open_connection(DB_PATH)
        _local.conn = conn
    return conn


def _open_connection(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA cache_size=-32000")   # 32 MB page cache
    conn.execute("PRAGMA temp_store=MEMORY")
    return conn


def close_connection():
    """Close the thread-local connection if open."""
    conn = getattr(_local, "conn", None)
    if conn:
        conn.close()
        _local.conn = None


def get_db():
    """Alias for get_connection() — returns sqlite3.Connection."""
    return get_connection()
