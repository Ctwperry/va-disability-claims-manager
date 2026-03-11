"""
Database schema creation and migration.
Call initialize_database() once at application startup.
"""
import sqlite3
import logging
from app.db.connection import get_connection

log = logging.getLogger(__name__)

CURRENT_VERSION = 1

# ---------------------------------------------------------------------------
# DDL Statements
# ---------------------------------------------------------------------------

_CREATE_VETERANS = """
CREATE TABLE IF NOT EXISTS veterans (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    full_name       TEXT NOT NULL,
    ssn_last4       TEXT,
    dob             TEXT,
    branch          TEXT,
    entry_date      TEXT,
    separation_date TEXT,
    discharge_type  TEXT,
    dd214_on_file   INTEGER DEFAULT 0,
    era             TEXT,
    notes           TEXT,
    created_at      TEXT DEFAULT (datetime('now')),
    updated_at      TEXT DEFAULT (datetime('now'))
);
"""

_CREATE_CLAIMS = """
CREATE TABLE IF NOT EXISTS claims (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    veteran_id              INTEGER NOT NULL REFERENCES veterans(id) ON DELETE CASCADE,
    condition_name          TEXT NOT NULL,
    vasrd_code              TEXT,
    body_system             TEXT,
    claim_type              TEXT DEFAULT 'direct',
    presumptive_basis       TEXT,
    has_diagnosis           INTEGER DEFAULT 0,
    diagnosis_source        TEXT,
    diagnosis_date          TEXT,
    has_inservice_event     INTEGER DEFAULT 0,
    inservice_source        TEXT,
    inservice_description   TEXT,
    inservice_date          TEXT,
    has_nexus               INTEGER DEFAULT 0,
    nexus_source            TEXT,
    nexus_type              TEXT DEFAULT 'direct',
    nexus_language_verified INTEGER DEFAULT 0,
    risk_missing_nexus      INTEGER DEFAULT 0,
    risk_no_continuity      INTEGER DEFAULT 0,
    risk_wrong_form         INTEGER DEFAULT 0,
    risk_negative_cp_likely INTEGER DEFAULT 0,
    status                  TEXT DEFAULT 'building',
    priority_rating         INTEGER,
    notes                   TEXT,
    created_at              TEXT DEFAULT (datetime('now')),
    updated_at              TEXT DEFAULT (datetime('now'))
);
"""

_CREATE_CLAIMS_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_claims_veteran ON claims(veteran_id);",
    "CREATE INDEX IF NOT EXISTS idx_claims_status ON claims(status);",
]

_CREATE_DOCUMENTS = """
CREATE TABLE IF NOT EXISTS documents (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    veteran_id       INTEGER NOT NULL REFERENCES veterans(id) ON DELETE CASCADE,
    claim_id         INTEGER REFERENCES claims(id) ON DELETE SET NULL,
    filename         TEXT NOT NULL,
    filepath         TEXT NOT NULL,
    file_hash        TEXT NOT NULL,
    doc_type         TEXT DEFAULT 'Other',
    doc_date         TEXT,
    source_facility  TEXT,
    author           TEXT,
    page_count       INTEGER DEFAULT 0,
    ocr_performed    INTEGER DEFAULT 0,
    ingestion_status TEXT DEFAULT 'pending',
    ingestion_error  TEXT,
    file_size_bytes  INTEGER,
    created_at       TEXT DEFAULT (datetime('now'))
);
"""

_CREATE_DOCUMENTS_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_documents_veteran ON documents(veteran_id);",
    "CREATE INDEX IF NOT EXISTS idx_documents_claim ON documents(claim_id);",
    "CREATE INDEX IF NOT EXISTS idx_documents_type ON documents(doc_type);",
    "CREATE UNIQUE INDEX IF NOT EXISTS idx_documents_hash ON documents(veteran_id, file_hash);",
]

_CREATE_DOCUMENT_PAGES = """
CREATE TABLE IF NOT EXISTS document_pages (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id  INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    page_number  INTEGER NOT NULL,
    raw_text     TEXT,
    char_count   INTEGER DEFAULT 0,
    has_image    INTEGER DEFAULT 0,
    UNIQUE(document_id, page_number)
);
"""

_CREATE_PAGES_INDEX = """
CREATE INDEX IF NOT EXISTS idx_pages_document ON document_pages(document_id);
"""

_CREATE_FTS5 = """
CREATE VIRTUAL TABLE IF NOT EXISTS document_search USING fts5(
    content='document_pages',
    content_rowid='id',
    raw_text,
    tokenize='porter unicode61'
);
"""

_CREATE_FTS_TRIGGERS = """
CREATE TRIGGER IF NOT EXISTS pages_ai
AFTER INSERT ON document_pages BEGIN
    INSERT INTO document_search(rowid, raw_text)
    VALUES (new.id, new.raw_text);
END;

CREATE TRIGGER IF NOT EXISTS pages_ad
AFTER DELETE ON document_pages BEGIN
    INSERT INTO document_search(document_search, rowid, raw_text)
    VALUES ('delete', old.id, old.raw_text);
END;

CREATE TRIGGER IF NOT EXISTS pages_au
AFTER UPDATE ON document_pages BEGIN
    INSERT INTO document_search(document_search, rowid, raw_text)
    VALUES ('delete', old.id, old.raw_text);
    INSERT INTO document_search(rowid, raw_text)
    VALUES (new.id, new.raw_text);
END;
"""

_CREATE_CLAIM_DOCUMENTS = """
CREATE TABLE IF NOT EXISTS claim_documents (
    claim_id    INTEGER NOT NULL REFERENCES claims(id) ON DELETE CASCADE,
    document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    role        TEXT DEFAULT 'supporting',
    notes       TEXT,
    linked_at   TEXT DEFAULT (datetime('now')),
    PRIMARY KEY (claim_id, document_id, role)
);
"""

_CREATE_SAVED_SEARCHES = """
CREATE TABLE IF NOT EXISTS saved_searches (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    veteran_id INTEGER REFERENCES veterans(id) ON DELETE CASCADE,
    label      TEXT NOT NULL,
    query_text TEXT NOT NULL,
    created_at TEXT DEFAULT (datetime('now'))
);
"""

_CREATE_VA_FORMS = """
CREATE TABLE IF NOT EXISTS va_forms (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    veteran_id  INTEGER NOT NULL REFERENCES veterans(id) ON DELETE CASCADE,
    claim_id    INTEGER REFERENCES claims(id) ON DELETE SET NULL,
    form_number TEXT NOT NULL,
    form_label  TEXT,
    status      TEXT DEFAULT 'draft',
    output_path TEXT,
    field_data  TEXT,
    created_at  TEXT DEFAULT (datetime('now')),
    updated_at  TEXT DEFAULT (datetime('now'))
);
"""

_CREATE_EXPORT_PACKAGES = """
CREATE TABLE IF NOT EXISTS export_packages (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    veteran_id       INTEGER NOT NULL REFERENCES veterans(id) ON DELETE CASCADE,
    package_type     TEXT DEFAULT 'full_claim',
    output_path      TEXT,
    claims_included  TEXT,
    created_at       TEXT DEFAULT (datetime('now'))
);
"""

_CREATE_APP_SETTINGS = """
CREATE TABLE IF NOT EXISTS app_settings (
    key   TEXT PRIMARY KEY,
    value TEXT
);
"""

_DEFAULT_SETTINGS = [
    ("db_version", str(CURRENT_VERSION)),
    ("tesseract_path", r"C:\Program Files\Tesseract-OCR\tesseract.exe"),
    ("default_export_dir", ""),
    ("active_veteran_id", ""),
    ("window_geometry", ""),
    ("theme", "light"),
]

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def initialize_database():
    """Create all tables and FTS5 index. Safe to call on every startup."""
    conn = get_connection()
    try:
        with conn:
            conn.execute(_CREATE_VETERANS)
            conn.execute(_CREATE_CLAIMS)
            for idx in _CREATE_CLAIMS_INDEXES:
                conn.execute(idx)
            conn.execute(_CREATE_DOCUMENTS)
            for idx in _CREATE_DOCUMENTS_INDEXES:
                conn.execute(idx)
            conn.execute(_CREATE_DOCUMENT_PAGES)
            conn.execute(_CREATE_PAGES_INDEX)
            conn.execute(_CREATE_FTS5)
            # Triggers must be created individually (can't use executescript inside a transaction)
            for stmt in _parse_trigger_statements(_CREATE_FTS_TRIGGERS):
                conn.execute(stmt)
            conn.execute(_CREATE_CLAIM_DOCUMENTS)
            conn.execute(_CREATE_SAVED_SEARCHES)
            conn.execute(_CREATE_VA_FORMS)
            conn.execute(_CREATE_EXPORT_PACKAGES)
            conn.execute(_CREATE_APP_SETTINGS)
            # Insert default settings only if they don't already exist
            for key, value in _DEFAULT_SETTINGS:
                conn.execute(
                    "INSERT OR IGNORE INTO app_settings (key, value) VALUES (?, ?)",
                    (key, value),
                )
        log.info("Database initialized successfully at %s", conn)
    except Exception as exc:
        log.exception("Failed to initialize database: %s", exc)
        raise


def get_setting(key: str, default: str = "") -> str:
    conn = get_connection()
    row = conn.execute(
        "SELECT value FROM app_settings WHERE key = ?", (key,)
    ).fetchone()
    return row["value"] if row else default


def set_setting(key: str, value: str):
    conn = get_connection()
    with conn:
        conn.execute(
            "INSERT OR REPLACE INTO app_settings (key, value) VALUES (?, ?)",
            (key, value),
        )


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _parse_trigger_statements(sql: str) -> list[str]:
    """Split a multi-trigger DDL block into individual statements."""
    statements = []
    current = []
    for line in sql.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("--"):
            continue
        current.append(line)
        if stripped == "END;":
            statements.append("\n".join(current))
            current = []
    return statements
