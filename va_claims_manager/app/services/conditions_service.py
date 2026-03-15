"""
Central loader for VASRD condition data and PACT Act enrichment.

Both ClaimPanel and ConditionsBrowserPanel use this to avoid duplicate
file reads. Results are LRU-cached so the JSON files are only parsed once
per process lifetime.

Public API:
    load_vasrd_codes() -> list[dict]        raw {code, name, system} dicts
    load_enriched_conditions() -> list[dict] same + is_presumptive, presumptive_basis, eligible_eras
    is_known_vasrd_code(code, known_codes=None) -> bool   validate user input against known list
"""
from __future__ import annotations
import json
from functools import lru_cache

from app.config import VASRD_CODES_PATH
from app.analysis.presumptive_data import enrich_vasrd_conditions


@lru_cache(maxsize=1)
def load_vasrd_codes() -> list[dict]:
    """Load raw VASRD diagnostic codes from JSON. Cached after first call."""
    try:
        with open(VASRD_CODES_PATH) as f:
            data = json.load(f)
        return data.get("codes", [])
    except Exception:
        return []


@lru_cache(maxsize=1)
def load_enriched_conditions() -> list[dict]:
    """
    Load VASRD codes enriched with PACT Act presumptive flags.
    Each entry gains: is_presumptive (bool), presumptive_basis (str), eligible_eras (list).
    Cached after first call.
    """
    return enrich_vasrd_conditions(load_vasrd_codes())


def is_known_vasrd_code(code: str, known_codes: list[dict] | None = None) -> bool:
    """
    Return True if code is empty/whitespace or matches a known VASRD diagnostic code.

    Args:
        code:        The code string to validate (raw user input — may have spaces).
        known_codes: Optional list of {code, name, system} dicts. If None, calls
                     load_vasrd_codes(). Pass explicitly in tests to avoid the LRU
                     cache complicating monkeypatching.

    Returns:
        True  — code is absent (empty / whitespace-only), or found in known_codes.
        False — code is non-empty and not in known_codes.
    """
    if not code or not code.strip():
        return True
    if known_codes is None:
        known_codes = load_vasrd_codes()
    return any(entry["code"] == code.strip() for entry in known_codes)
