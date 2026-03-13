"""
CRUD operations for claims.
"""
from typing import Optional
from app.db.connection import get_connection
from app.core.claim import Claim


def create(c: Claim) -> int:
    conn = get_connection()
    with conn:
        cur = conn.execute(
            """
            INSERT INTO claims (
                veteran_id, condition_name, vasrd_code, body_system, claim_type,
                presumptive_basis, has_diagnosis, diagnosis_source, diagnosis_date,
                has_inservice_event, inservice_source, inservice_description, inservice_date,
                has_nexus, nexus_source, nexus_type, nexus_language_verified,
                risk_missing_nexus, risk_no_continuity, risk_wrong_form, risk_negative_cp_likely,
                status, priority_rating, notes,
                effective_date, effective_date_basis, secondary_to_claim_id,
                first_treatment_date, continuity_notes, symptom_log
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            _params(c),
        )
    return cur.lastrowid


def update(c: Claim):
    conn = get_connection()
    with conn:
        conn.execute(
            """
            UPDATE claims SET
                condition_name=?, vasrd_code=?, body_system=?, claim_type=?,
                presumptive_basis=?, has_diagnosis=?, diagnosis_source=?, diagnosis_date=?,
                has_inservice_event=?, inservice_source=?, inservice_description=?, inservice_date=?,
                has_nexus=?, nexus_source=?, nexus_type=?, nexus_language_verified=?,
                risk_missing_nexus=?, risk_no_continuity=?, risk_wrong_form=?, risk_negative_cp_likely=?,
                status=?, priority_rating=?, notes=?,
                effective_date=?, effective_date_basis=?, secondary_to_claim_id=?,
                first_treatment_date=?, continuity_notes=?, symptom_log=?,
                updated_at=datetime('now')
            WHERE id=?
            """,
            _params(c)[1:] + (c.id,),
        )


def delete(claim_id: int):
    conn = get_connection()
    with conn:
        conn.execute("DELETE FROM claims WHERE id=?", (claim_id,))


def get_by_id(claim_id: int) -> Optional[Claim]:
    conn = get_connection()
    row = conn.execute("SELECT * FROM claims WHERE id=?", (claim_id,)).fetchone()
    return Claim.from_row(row) if row else None


def get_all(veteran_id: int) -> list[Claim]:
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM claims WHERE veteran_id=? ORDER BY condition_name COLLATE NOCASE",
        (veteran_id,),
    ).fetchall()
    return [Claim.from_row(r) for r in rows]


def count_complete(veteran_id: int) -> int:
    conn = get_connection()
    row = conn.execute(
        """SELECT COUNT(*) AS n FROM claims
           WHERE veteran_id=? AND has_diagnosis=1 AND has_inservice_event=1 AND has_nexus=1""",
        (veteran_id,),
    ).fetchone()
    return row["n"] if row else 0


def count_total(veteran_id: int) -> int:
    conn = get_connection()
    row = conn.execute(
        "SELECT COUNT(*) AS n FROM claims WHERE veteran_id=?", (veteran_id,)
    ).fetchone()
    return row["n"] if row else 0


def _params(c: Claim) -> tuple:
    return (
        c.veteran_id, c.condition_name, c.vasrd_code, c.body_system, c.claim_type,
        c.presumptive_basis, int(c.has_diagnosis), c.diagnosis_source, c.diagnosis_date,
        int(c.has_inservice_event), c.inservice_source, c.inservice_description, c.inservice_date,
        int(c.has_nexus), c.nexus_source, c.nexus_type, int(c.nexus_language_verified),
        int(c.risk_missing_nexus), int(c.risk_no_continuity), int(c.risk_wrong_form),
        int(c.risk_negative_cp_likely), c.status, c.priority_rating, c.notes,
        c.effective_date or "", c.effective_date_basis or "", c.secondary_to_claim_id,
        c.first_treatment_date or "", c.continuity_notes or "", c.symptom_log or "[]",
    )
