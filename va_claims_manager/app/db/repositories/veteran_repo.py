"""
CRUD operations for veterans.
"""
from typing import Optional
from app.db.connection import get_connection
from app.core.veteran import Veteran


def create(v: Veteran) -> int:
    """Insert a new veteran and return the new row id."""
    conn = get_connection()
    with conn:
        cur = conn.execute(
            """
            INSERT INTO veterans
                (full_name, ssn_last4, dob, branch, entry_date, separation_date,
                 discharge_type, dd214_on_file, era, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                v.full_name, v.ssn_last4, v.dob, v.branch,
                v.entry_date, v.separation_date, v.discharge_type,
                int(v.dd214_on_file), v.era, v.notes,
            ),
        )
    return cur.lastrowid


def update(v: Veteran):
    """Update all editable fields for an existing veteran."""
    conn = get_connection()
    with conn:
        conn.execute(
            """
            UPDATE veterans SET
                full_name       = ?,
                ssn_last4       = ?,
                dob             = ?,
                branch          = ?,
                entry_date      = ?,
                separation_date = ?,
                discharge_type  = ?,
                dd214_on_file   = ?,
                era             = ?,
                notes           = ?,
                updated_at      = datetime('now')
            WHERE id = ?
            """,
            (
                v.full_name, v.ssn_last4, v.dob, v.branch,
                v.entry_date, v.separation_date, v.discharge_type,
                int(v.dd214_on_file), v.era, v.notes, v.id,
            ),
        )


def delete(veteran_id: int):
    conn = get_connection()
    with conn:
        conn.execute("DELETE FROM veterans WHERE id = ?", (veteran_id,))


def get_by_id(veteran_id: int) -> Optional[Veteran]:
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM veterans WHERE id = ?", (veteran_id,)
    ).fetchone()
    return Veteran.from_row(row) if row else None


def get_all() -> list[Veteran]:
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM veterans ORDER BY full_name COLLATE NOCASE"
    ).fetchall()
    return [Veteran.from_row(r) for r in rows]


def count() -> int:
    conn = get_connection()
    row = conn.execute("SELECT COUNT(*) AS n FROM veterans").fetchone()
    return row["n"]
