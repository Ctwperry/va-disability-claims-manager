"""
PACT Act / Presumptive condition utility functions.

Merges pact_act_conditions.json with VASRD codes to enrich conditions
with is_presumptive, presumptive_basis, and eligible_eras fields.
"""
from __future__ import annotations
import json
import re

from app.config import PACT_ACT_PATH


def load_pact_categories() -> dict:
    """Load all PACT Act categories from JSON file."""
    try:
        with open(PACT_ACT_PATH) as f:
            return json.load(f)
    except Exception:
        return {}


def get_era_recommendations(era: str) -> list[dict]:
    """
    Return list of {condition_name, basis, category_label, eligible_eras}
    for all PACT conditions that match the veteran's service era.
    """
    if not era:
        return []

    data = load_pact_categories()
    era_lower = era.lower()
    results = []

    for _key, category in data.items():
        eligible_eras = category.get("exposure_eras", [])
        era_match = any(
            e.lower() in era_lower or era_lower in e.lower()
            for e in eligible_eras
        )
        if not era_match:
            continue
        category_label = category.get("label", "Presumptive Condition")
        basis = category_label
        for condition_name in category.get("conditions", []):
            results.append({
                "condition_name": condition_name,
                "basis": basis,
                "category_label": category_label,
                "eligible_eras": eligible_eras,
            })

    return results


def get_era_categories(era: str) -> list[dict]:
    """
    Return list of {label, conditions: [...], eligible_eras} grouped by PACT category
    for conditions that match the veteran's service era.
    """
    if not era:
        return []

    data = load_pact_categories()
    era_lower = era.lower()
    result = []

    for _key, category in data.items():
        eligible_eras = category.get("exposure_eras", [])
        era_match = any(
            e.lower() in era_lower or era_lower in e.lower()
            for e in eligible_eras
        )
        if not era_match:
            continue
        result.append({
            "label": category.get("label", "Presumptive"),
            "conditions": category.get("conditions", []),
            "eligible_eras": eligible_eras,
        })

    return result


def enrich_vasrd_conditions(vasrd_codes: list[dict]) -> list[dict]:
    """
    Add presumptive fields to each VASRD condition dict.

    Each enriched entry gains:
      is_presumptive (bool), presumptive_basis (str), eligible_eras (list[str])
    """
    data = load_pact_categories()

    # Build keyword → (basis, eras) mapping from PACT data
    keyword_map: dict[str, tuple[str, list]] = {}
    for category in data.values():
        basis = category.get("label", "Presumptive")
        eras = category.get("exposure_eras", [])
        for condition in category.get("conditions", []):
            # Strip parenthetical notes and lower-case
            clean = re.sub(r"\s*\(.*?\)", "", condition).lower().strip()
            keyword_map[clean] = (basis, eras)
            # Also index significant sub-words (≥4 chars) that weren't already mapped
            for word in clean.split():
                if len(word) >= 5 and word not in keyword_map:
                    keyword_map[word] = (basis, eras)

    enriched = []
    for code_entry in vasrd_codes:
        entry = dict(code_entry)
        name_lower = entry["name"].lower()

        match_basis = ""
        match_eras: list = []
        for keyword, (basis, eras) in keyword_map.items():
            if keyword in name_lower or name_lower in keyword:
                match_basis = basis
                match_eras = eras
                break

        entry["is_presumptive"] = bool(match_basis)
        entry["presumptive_basis"] = match_basis
        entry["eligible_eras"] = match_eras
        enriched.append(entry)

    return enriched
