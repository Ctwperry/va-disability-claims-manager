"""
FTS5 full-text search engine.
Uses SQLite's built-in FTS5 virtual table with Porter stemming and BM25 ranking.
"""
import logging
import re
from dataclasses import dataclass
from typing import Optional

from app.config import SEARCH_RESULT_LIMIT, SEARCH_SNIPPET_WORDS
from app.db.connection import get_connection

log = logging.getLogger(__name__)


@dataclass
class SearchResult:
    doc_id: int
    page_number: int
    filename: str
    doc_type: str
    doc_date: str
    snippet: str       # HTML snippet with <mark> tags
    rank: float        # BM25 score (lower = more relevant)
    page_id: int       # document_pages.id


def search(
    query: str,
    veteran_id: int,
    doc_type_filter: Optional[str] = None,
    claim_id_filter: Optional[int] = None,
    limit: int = SEARCH_RESULT_LIMIT,
) -> list[SearchResult]:
    """
    Execute a full-text search across all documents for a veteran.

    Args:
        query: Natural language or FTS5 query string.
        veteran_id: Restrict to documents belonging to this veteran.
        doc_type_filter: Optional doc_type to restrict results.
        claim_id_filter: Optional claim_id to restrict results.
        limit: Maximum number of results.

    Returns:
        List of SearchResult objects ordered by relevance (best first).
    """
    if not query.strip():
        return []

    fts_query = _build_fts_query(query)
    if not fts_query:
        return []

    conn = get_connection()

    where_clauses = ["document_search MATCH ?", "d.veteran_id = ?"]
    params: list = [fts_query, veteran_id]

    if doc_type_filter:
        where_clauses.append("d.doc_type = ?")
        params.append(doc_type_filter)
    if claim_id_filter is not None:
        where_clauses.append("d.claim_id = ?")
        params.append(claim_id_filter)

    params.append(limit)

    sql = f"""
        SELECT
            dp.id          AS page_id,
            dp.document_id AS doc_id,
            dp.page_number,
            d.filename,
            d.doc_type,
            d.doc_date,
            snippet(document_search, 0, '<mark>', '</mark>', ' ... ', {SEARCH_SNIPPET_WORDS}) AS snippet,
            document_search.rank
        FROM document_search
        JOIN document_pages dp ON document_search.rowid = dp.id
        JOIN documents d ON dp.document_id = d.id
        WHERE {' AND '.join(where_clauses)}
        ORDER BY rank
        LIMIT ?
    """

    try:
        rows = conn.execute(sql, params).fetchall()
    except Exception as exc:
        log.error("FTS5 search failed (query=%r): %s", fts_query, exc)
        # Try simple MATCH fallback
        return _simple_search(query, veteran_id, doc_type_filter, claim_id_filter, limit)

    return [
        SearchResult(
            doc_id=r["doc_id"],
            page_number=r["page_number"],
            filename=r["filename"],
            doc_type=r["doc_type"],
            doc_date=r["doc_date"] or "",
            snippet=r["snippet"] or "",
            rank=r["rank"],
            page_id=r["page_id"],
        )
        for r in rows
    ]


def _build_fts_query(user_input: str) -> str:
    """
    Convert user input to FTS5 syntax.

    Rules:
    - Quoted phrases are kept as-is: "at least as likely as not"
    - Multiple words outside quotes are joined with AND NEAR/5
    - Special characters are escaped
    """
    user_input = user_input.strip()
    if not user_input:
        return ""

    # If already looks like FTS5 syntax (contains AND/OR/NEAR/NOT), use as-is
    if re.search(r'\b(AND|OR|NOT|NEAR)\b', user_input):
        return user_input

    # Extract quoted phrases first
    quoted = re.findall(r'"[^"]*"', user_input)
    remainder = re.sub(r'"[^"]*"', '', user_input).strip()

    # Tokenize remainder
    tokens = [_escape_fts_token(t) for t in remainder.split() if t]

    parts = quoted + tokens

    if not parts:
        return ""

    if len(parts) == 1:
        return parts[0]

    # Join with AND for multi-term queries
    return " AND ".join(parts)


def _escape_fts_token(token: str) -> str:
    """Escape a single FTS5 token (remove special chars)."""
    # FTS5 special characters: " ( ) * : ^
    cleaned = re.sub(r'[\"()*:^]', '', token)
    return cleaned if cleaned else '""'


def _simple_search(query, veteran_id, doc_type_filter, claim_id_filter, limit) -> list[SearchResult]:
    """Fallback: simple LIKE search when FTS5 query is malformed."""
    conn = get_connection()
    like_term = f"%{query.strip()[:100]}%"
    where = ["d.veteran_id = ?", "dp.raw_text LIKE ?"]
    params: list = [veteran_id, like_term]
    if doc_type_filter:
        where.append("d.doc_type = ?")
        params.append(doc_type_filter)
    params.append(limit)

    sql = f"""
        SELECT dp.id AS page_id, dp.document_id AS doc_id, dp.page_number,
               d.filename, d.doc_type, d.doc_date, dp.raw_text AS snippet, 0.0 AS rank
        FROM document_pages dp
        JOIN documents d ON dp.document_id = d.id
        WHERE {' AND '.join(where)}
        LIMIT ?
    """
    try:
        rows = conn.execute(sql, params).fetchall()
    except Exception:
        return []

    results = []
    for r in rows:
        # Extract a snippet manually
        raw = r["snippet"] or ""
        idx = raw.lower().find(query.lower()[:50])
        if idx >= 0:
            start = max(0, idx - 80)
            end = min(len(raw), idx + 200)
            snip = raw[start:end].replace(
                raw[idx:idx + len(query)],
                f"<mark>{raw[idx:idx + len(query)]}</mark>",
                1,
            )
        else:
            snip = raw[:200]
        results.append(SearchResult(
            doc_id=r["doc_id"], page_number=r["page_number"],
            filename=r["filename"], doc_type=r["doc_type"],
            doc_date=r["doc_date"] or "", snippet=snip,
            rank=0.0, page_id=r["page_id"],
        ))
    return results


def get_page_text(page_id: int) -> str:
    """Return the full raw text of a specific page."""
    conn = get_connection()
    row = conn.execute(
        "SELECT raw_text FROM document_pages WHERE id=?", (page_id,)
    ).fetchone()
    return row["raw_text"] if row else ""
