"""
Tests for app.db.encryption — key management and plaintext migration.
"""
import sqlite3 as stdlib_sqlite3
from pathlib import Path
import pytest


# ── Key management ────────────────────────────────────────────────────────────

def test_set_test_key_and_get_db_key():
    """set_test_key() must make the key available via get_db_key()."""
    from app.db.encryption import set_test_key, get_db_key
    set_test_key("my-test-key")
    assert get_db_key() == "my-test-key"


def test_get_db_key_raises_when_not_initialized():
    """get_db_key() must raise if no key has been set."""
    from app.db import encryption as enc_mod
    original = enc_mod._db_key
    try:
        enc_mod._db_key = None
        with pytest.raises(RuntimeError, match="not initialized"):
            enc_mod.get_db_key()
    finally:
        enc_mod._db_key = original


# ── Plaintext detection ───────────────────────────────────────────────────────

def test_is_plaintext_db_detects_unencrypted(tmp_path):
    """A standard sqlite3 database should be detected as plaintext."""
    from app.db.encryption import is_plaintext_db

    db = tmp_path / "plain.db"
    conn = stdlib_sqlite3.connect(str(db))
    conn.execute("CREATE TABLE t (id INTEGER)")
    conn.close()

    assert is_plaintext_db(db) is True


def test_is_plaintext_db_rejects_encrypted(tmp_path):
    """An encrypted sqlcipher3 database should NOT be detected as plaintext."""
    import sqlcipher3
    from app.db.encryption import is_plaintext_db

    db = tmp_path / "encrypted.db"
    conn = sqlcipher3.connect(str(db))
    conn.execute('PRAGMA key = "secret"')
    conn.execute("CREATE TABLE t (id INTEGER)")
    conn.close()

    assert is_plaintext_db(db) is False


def test_is_plaintext_db_returns_false_for_missing_file(tmp_path):
    from app.db.encryption import is_plaintext_db
    assert is_plaintext_db(tmp_path / "nonexistent.db") is False


# ── Migration ─────────────────────────────────────────────────────────────────

def test_migrate_plaintext_to_encrypted(tmp_path):
    """Migration must produce an encrypted DB readable only with the correct key."""
    import sqlcipher3
    from app.db.encryption import migrate_plaintext_to_encrypted, is_plaintext_db

    db = tmp_path / "test.db"
    key = "migration-test-key"

    # Create a plaintext DB with some data
    conn = stdlib_sqlite3.connect(str(db))
    conn.execute("CREATE TABLE veterans (id INTEGER, name TEXT)")
    conn.execute("INSERT INTO veterans VALUES (1, 'John Doe')")
    conn.commit()
    conn.close()
    assert is_plaintext_db(db) is True

    # Migrate
    backup = migrate_plaintext_to_encrypted(db, key)

    # Original path should now be encrypted
    assert is_plaintext_db(db) is False
    assert backup.exists()
    assert backup.suffix == ".bak"

    # Verify data is accessible with the correct key
    conn = sqlcipher3.connect(str(db))
    conn.execute(f'PRAGMA key = "{key}"')
    row = conn.execute("SELECT name FROM veterans WHERE id = 1").fetchone()
    conn.close()
    assert row[0] == "John Doe"


def test_migrate_preserves_all_tables(tmp_path):
    """Migration must preserve all tables and data, including FTS5."""
    import sqlcipher3
    from app.db.encryption import migrate_plaintext_to_encrypted

    db = tmp_path / "test.db"
    key = "fts-test-key"

    # Create a plaintext DB with FTS5
    conn = stdlib_sqlite3.connect(str(db))
    conn.execute("CREATE TABLE docs (id INTEGER, text TEXT)")
    conn.execute("INSERT INTO docs VALUES (1, 'service treatment record')")
    conn.execute(
        "CREATE VIRTUAL TABLE docs_fts USING fts5(text, content='docs', content_rowid='id')"
    )
    conn.execute("INSERT INTO docs_fts(rowid, text) VALUES (1, 'service treatment record')")
    conn.commit()
    conn.close()

    migrate_plaintext_to_encrypted(db, key)

    # Verify FTS5 works in encrypted DB
    conn = sqlcipher3.connect(str(db))
    conn.execute(f'PRAGMA key = "{key}"')
    row = conn.execute("SELECT * FROM docs_fts WHERE docs_fts MATCH 'treatment'").fetchone()
    conn.close()
    assert row is not None


def test_encrypted_db_unreadable_without_key(tmp_path):
    """An encrypted DB must not be openable with stdlib sqlite3."""
    import sqlcipher3
    from app.db.encryption import migrate_plaintext_to_encrypted

    db = tmp_path / "test.db"
    key = "secret-key"

    conn = stdlib_sqlite3.connect(str(db))
    conn.execute("CREATE TABLE t (id INTEGER)")
    conn.commit()
    conn.close()

    migrate_plaintext_to_encrypted(db, key)

    # stdlib sqlite3 should fail to read any data
    conn = stdlib_sqlite3.connect(str(db))
    with pytest.raises(Exception):
        conn.execute("SELECT * FROM t")
    conn.close()


# ── Connection integration ────────────────────────────────────────────────────

def test_connection_uses_encryption_key(tmp_path):
    """get_connection() should produce a working encrypted DB connection."""
    from app.db.encryption import set_test_key
    import app.db.connection as conn_mod

    set_test_key("integration-test-key")

    conn = conn_mod.get_connection()
    conn.execute("CREATE TABLE test_enc (val TEXT)")
    conn.execute("INSERT INTO test_enc VALUES ('encrypted')")
    row = conn.execute("SELECT val FROM test_enc").fetchone()
    assert row["val"] == "encrypted"
