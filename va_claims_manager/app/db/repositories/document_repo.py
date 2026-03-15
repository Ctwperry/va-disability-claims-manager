"""
CRUD operations for documents and document_pages.
"""
from typing import Optional
from app.db.connection import get_connection
from app.core.document import Document


def create(doc: Document) -> int:
    conn = get_connection()
    with conn:
        cur = conn.execute(
            """
            INSERT INTO documents
                (veteran_id, claim_id, filename, filepath, file_hash, doc_type,
                 doc_date, source_facility, author, page_count, ocr_performed,
                 ingestion_status, ingestion_error, file_size_bytes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                doc.veteran_id, doc.claim_id, doc.filename, doc.filepath,
                doc.file_hash, doc.doc_type, doc.doc_date, doc.source_facility,
                doc.author, doc.page_count, int(doc.ocr_performed),
                doc.ingestion_status, doc.ingestion_error, doc.file_size_bytes,
            ),
        )
    return cur.lastrowid


def update_status(doc_id: int, status: str, error: str = "", page_count: int = -1,
                  ocr_performed: bool = False):
    conn = get_connection()
    with conn:
        if page_count >= 0:
            conn.execute(
                """UPDATE documents SET ingestion_status=?, ingestion_error=?,
                   page_count=?, ocr_performed=? WHERE id=?""",
                (status, error, page_count, int(ocr_performed), doc_id),
            )
        else:
            conn.execute(
                "UPDATE documents SET ingestion_status=?, ingestion_error=? WHERE id=?",
                (status, error, doc_id),
            )


def update_metadata(doc_id: int, doc_type: str = None, doc_date: str = None,
                    source_facility: str = None, author: str = None):
    conn = get_connection()
    with conn:
        conn.execute(
            """
            UPDATE documents SET
                doc_type        = COALESCE(?, doc_type),
                doc_date        = COALESCE(?, doc_date),
                source_facility = COALESCE(?, source_facility),
                author          = COALESCE(?, author)
            WHERE id=?
            """,
            (doc_type, doc_date, source_facility, author, doc_id),
        )


def hash_exists(veteran_id: int, file_hash: str) -> bool:
    conn = get_connection()
    row = conn.execute(
        "SELECT id FROM documents WHERE veteran_id=? AND file_hash=?",
        (veteran_id, file_hash),
    ).fetchone()
    return row is not None


def get_by_id(doc_id: int) -> Optional[Document]:
    conn = get_connection()
    row = conn.execute("SELECT * FROM documents WHERE id=?", (doc_id,)).fetchone()
    return Document.from_row(row) if row else None


def get_all(veteran_id: int, doc_type: str = None, claim_id: int = None) -> list[Document]:
    conn = get_connection()
    if doc_type and claim_id is not None:
        sql = "SELECT * FROM documents WHERE veteran_id=? AND doc_type=? AND claim_id=? ORDER BY created_at DESC"
        params = (veteran_id, doc_type, claim_id)
    elif doc_type:
        sql = "SELECT * FROM documents WHERE veteran_id=? AND doc_type=? ORDER BY created_at DESC"
        params = (veteran_id, doc_type)
    elif claim_id is not None:
        sql = "SELECT * FROM documents WHERE veteran_id=? AND claim_id=? ORDER BY created_at DESC"
        params = (veteran_id, claim_id)
    else:
        sql = "SELECT * FROM documents WHERE veteran_id=? ORDER BY created_at DESC"
        params = (veteran_id,)
    rows = conn.execute(sql, params).fetchall()
    return [Document.from_row(r) for r in rows]


def delete(doc_id: int):
    conn = get_connection()
    with conn:
        conn.execute("DELETE FROM documents WHERE id=?", (doc_id,))


def insert_pages(doc_id: int, pages: list[dict]):
    """Bulk insert document pages. pages = [{'page_number': n, 'raw_text': '...'}]"""
    conn = get_connection()
    data = [
        (doc_id, p["page_number"], p["raw_text"], len(p["raw_text"]), p.get("has_image", 0))
        for p in pages
    ]
    with conn:
        conn.executemany(
            "INSERT OR REPLACE INTO document_pages (document_id, page_number, raw_text, char_count, has_image) VALUES (?, ?, ?, ?, ?)",
            data,
        )


def get_page_count(doc_id: int) -> int:
    conn = get_connection()
    row = conn.execute(
        "SELECT COUNT(*) AS n FROM document_pages WHERE document_id=?", (doc_id,)
    ).fetchone()
    return row["n"] if row else 0


def count(veteran_id: int) -> int:
    conn = get_connection()
    row = conn.execute(
        "SELECT COUNT(*) AS n FROM documents WHERE veteran_id=? AND ingestion_status='complete'",
        (veteran_id,),
    ).fetchone()
    return row["n"] if row else 0
