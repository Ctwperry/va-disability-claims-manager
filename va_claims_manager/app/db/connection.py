"""
SQLite database connection management (encrypted via SQLCipher).
- AES-256 encryption at rest via sqlcipher3
- WAL mode for non-blocking reads during document ingestion
- Foreign key enforcement
- Thread-local connections: each thread owns its own connection,
  so SQLite's default check_same_thread guard is never bypassed.
"""
import sqlcipher3 as sqlite3
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
    from app.db.encryption import get_db_key

    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))

    # PRAGMA key must be the FIRST statement on an encrypted database.
    key = get_db_key()
    conn.execute(f'PRAGMA key = "{key}"')

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
