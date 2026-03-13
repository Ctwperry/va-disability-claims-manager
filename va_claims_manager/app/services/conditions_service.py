"""
Central loader for VASRD condition data and PACT Act enrichment.

Both ClaimPanel and ConditionsBrowserPanel use this to avoid duplicate
file reads. Results are LRU-cached so the JSON files are only parsed once
per process lifetime.

Public API:
    load_vasrd_codes() -> list[dict]        raw {code, name, system} dicts
    load_enriched_conditions() -> list[dict] same + is_presumptive, presumptive_basis, eligible_eras
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
