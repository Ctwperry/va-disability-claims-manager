"""
Validated JSON parsers for data blobs stored in SQLite.

Raw json.loads() is unsafe on database-sourced strings: a malformed or
malicious value can cause TypeError crashes (wrong type accessed via .get())
or DoS through deeply nested structures. These parsers enforce the known
schema of each blob type, returning safe empty defaults on any violation.

No external dependencies — stdlib json only.
"""
from __future__ import annotations
import json

# Maximum length of any individual string field. Prevents DoS through
# extremely large strings that would consume memory in UI table cells.
MAX_FIELD_LEN = 2000

# Known string keys for the symptom log entry schema.
_SYMPTOM_LOG_KEYS = ("date", "source", "complaint", "diagnosis", "treatment")


def parse_symptom_log(json_str: str | None) -> list[dict]:
    """
    Parse and validate a symptom log JSON blob from claims.symptom_log.

    Expected schema: a JSON array of objects, each with string fields
    date, source, complaint, diagnosis, treatment (all optional).

    Any entry that is not a dict is silently dropped. Non-string field
    values are coerced to str (None → ""). Strings longer than
    MAX_FIELD_LEN are truncated. Returns [] on any parse error or if
    the root value is not a list.

    Args:
        json_str: Raw JSON string from the database, or None/empty.

    Returns:
        List of validated entry dicts, always safe to iterate.
    """
    if not json_str:
        return []
    try:
        data = json.loads(json_str)
    except Exception:
        return []
    if not isinstance(data, list):
        return []
    entries = []
    for item in data:
        if not isinstance(item, dict):
            continue
        entry = {}
        for key in _SYMPTOM_LOG_KEYS:
            raw = item.get(key)
            if raw is None:
                entry[key] = ""
            else:
                val = str(raw)
                entry[key] = val[:MAX_FIELD_LEN]
        entries.append(entry)
    return entries


def parse_evidence_notes(json_str: str | None) -> dict:
    """
    Parse and validate an evidence notes JSON blob from claim_documents.notes.

    Expected schema: a JSON object with:
      - pages: list of dicts (page_number, keyword, snippet)
      - auto_detected: bool

    Returns {} on parse error or if the root value is not a dict.
    Replaces a non-list "pages" with []. Skips non-dict page entries.
    Coerces auto_detected to bool.

    Args:
        json_str: Raw JSON string from the database, or None/empty.

    Returns:
        Validated notes dict, always safe to call .get() on.
    """
    if not json_str:
        return {}
    try:
        data = json.loads(json_str)
    except Exception:
        return {}
    if not isinstance(data, dict):
        return {}

    pages_raw = data.get("pages", [])
    if not isinstance(pages_raw, list):
        pages_raw = []
    pages = [p for p in pages_raw if isinstance(p, dict)]

    return {
        "pages": pages,
        "auto_detected": bool(data.get("auto_detected", False)),
    }
