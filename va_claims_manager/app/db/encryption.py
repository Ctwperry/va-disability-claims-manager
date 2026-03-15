"""
Database encryption key management.

Uses the OS keychain (Windows Credential Manager, macOS Keychain,
Linux Secret Service) to store a 256-bit encryption key for SQLCipher.
The key is generated on first launch and never stored on the filesystem.

Public API:
    ensure_key()          Retrieve or generate the DB encryption key.
    get_db_key() -> str   Return the current key (must call ensure_key() first).
    set_test_key(key)     Override the key for testing.
    is_plaintext_db(path) Check if a DB file is unencrypted.
    migrate_plaintext_to_encrypted(path, key)  Convert plaintext DB to encrypted.
"""
from __future__ import annotations

import logging
import os
import secrets
from pathlib import Path

log = logging.getLogger(__name__)

# Module-level key cache — set once at startup, read by connection.py
_db_key: str | None = None


def get_db_key() -> str:
    """Return the current DB encryption key.

    Raises RuntimeError if ensure_key() has not been called yet.
    """
    if _db_key is None:
        raise RuntimeError(
            "DB encryption key not initialized. Call ensure_key() at startup."
        )
    return _db_key


def ensure_key() -> str:
    """Retrieve the encryption key from the OS keychain, or generate a new one.

    On first launch the key is generated as 64 hex chars (256 bits) and stored
    in the OS keychain.  On subsequent launches the stored key is returned.

    Returns:
        The hex-encoded encryption key string.
    """
    global _db_key
    import keyring
    from app.config import KEYCHAIN_SERVICE, KEYCHAIN_ACCOUNT

    key = keyring.get_password(KEYCHAIN_SERVICE, KEYCHAIN_ACCOUNT)
    if key is None:
        key = secrets.token_hex(32)  # 256-bit key as 64 hex chars
        keyring.set_password(KEYCHAIN_SERVICE, KEYCHAIN_ACCOUNT, key)
        log.info("Generated and stored new database encryption key in OS keychain")
    else:
        log.debug("Retrieved database encryption key from OS keychain")

    _db_key = key
    return key


def set_test_key(key: str) -> None:
    """Set the encryption key directly (used by test fixtures)."""
    global _db_key
    _db_key = key


def is_plaintext_db(db_path: Path) -> bool:
    """Return True if the file at db_path is an unencrypted SQLite database.

    Plaintext SQLite files start with the 16-byte header "SQLite format 3\\0".
    Encrypted files (SQLCipher) have randomised bytes in the header.
    """
    try:
        with open(db_path, "rb") as f:
            header = f.read(16)
        return header[:6] == b"SQLite"
    except (FileNotFoundError, PermissionError, IsADirectoryError):
        return False


def migrate_plaintext_to_encrypted(db_path: Path, key: str) -> Path:
    """Convert a plaintext SQLite database to an encrypted SQLCipher database.

    Strategy:
        1. Open the plaintext DB with stdlib sqlite3 and dump all SQL.
        2. Create a new encrypted DB with sqlcipher3 + PRAGMA key.
        3. Replay the dump into the encrypted DB.
        4. Rename: original → .plaintext.bak, encrypted → original name.

    Args:
        db_path: Path to the existing plaintext database.
        key:     Encryption key to use for the new database.

    Returns:
        Path to the plaintext backup file.
    """
    import sqlite3
    import sqlcipher3

    encrypted_path = db_path.with_suffix(".db.enc")

    # Step 1 — dump plaintext
    old_conn = sqlite3.connect(str(db_path))
    old_conn.row_factory = None  # iterdump doesn't need Row
    dump_statements = list(old_conn.iterdump())
    old_conn.close()

    # Step 2 — replay into encrypted DB
    #
    # iterdump() emits FTS5 virtual tables via PRAGMA writable_schema + shadow
    # table DDL.  The shadow tables (e.g. docs_fts_data, docs_fts_config) are
    # created and populated via separate CREATE TABLE + INSERT statements,
    # which is correct.  However, iterdump also emits a bare INSERT into the
    # virtual table name itself (e.g. INSERT INTO "docs_fts"), which fails
    # because the virtual table isn't created until writable_schema completes.
    #
    # Detect FTS5 virtual table names from the writable_schema INSERT and
    # filter out the bare INSERT INTO "<vtable>" statements.
    fts_vtables: set[str] = set()
    for stmt in dump_statements:
        if "sqlite_master" in stmt and "fts5" in stmt.lower():
            # Extract the virtual table name from the writable_schema INSERT
            # Format: INSERT INTO sqlite_master(...) VALUES('table','NAME',...)
            parts = stmt.split("VALUES(")
            if len(parts) == 2:
                fields = parts[1].split(",")
                if len(fields) >= 2:
                    vt_name = fields[1].strip().strip("'\"")
                    fts_vtables.add(vt_name)

    filtered = []
    for stmt in dump_statements:
        if stmt.startswith('INSERT INTO "') and fts_vtables:
            # Extract the target table name
            target = stmt.split('"')[1]
            # Skip INSERT into the virtual table itself (not its shadow tables)
            if target in fts_vtables:
                continue
        filtered.append(stmt)

    new_conn = sqlcipher3.connect(str(encrypted_path))
    new_conn.execute(f"PRAGMA key = \"{key}\"")
    new_conn.execute("PRAGMA journal_mode=WAL")
    new_conn.execute("PRAGMA foreign_keys=ON")
    new_conn.executescript("\n".join(filtered))
    new_conn.close()

    # Step 3 — swap files
    backup_path = db_path.with_suffix(".db.plaintext.bak")
    os.replace(str(db_path), str(backup_path))
    os.replace(str(encrypted_path), str(db_path))

    # Clean up stale WAL/SHM files from the plaintext DB
    for suffix in ("-wal", "-shm"):
        wal_file = Path(str(db_path) + suffix)
        if wal_file.exists():
            wal_file.unlink()

    log.info("Migrated plaintext database to encrypted format")
    log.info("Plaintext backup saved at: %s", backup_path)
    return backup_path
