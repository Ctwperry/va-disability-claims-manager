"""
VA Federal Benefits loader and rating-tier lookup.

Keeps benefits data separate from VASRD/conditions data.
Benefits are cumulative: a veteran at 70% receives all benefits
from every threshold <= 70%.

Public API:
    load_benefits_data() -> dict          raw JSON (LRU-cached)
    get_benefits_for_rating(rating) -> list[dict]   cumulative benefit list
    CATEGORY_LABELS -> dict[str, str]     display names for each category key
"""
from __future__ import annotations
import json
from functools import lru_cache

from app.config import BENEFITS_DATA_PATH


@lru_cache(maxsize=1)
def load_benefits_data() -> dict:
    """Load benefits JSON from disk. Cached after first call."""
    try:
        with open(BENEFITS_DATA_PATH) as f:
            return json.load(f)
    except Exception:
        return {"thresholds": {}, "category_labels": {}}


def get_benefits_for_rating(rating: int, tdiu_eligible: bool = False) -> list[dict]:
    """
    Return a cumulative list of benefit dicts for the given combined rating.

    Each dict has:
        threshold   int     — rating level where this benefit first unlocks
        category    str     — category key (e.g. "healthcare")
        category_label str  — human-readable category name
        name        str     — benefit name
        detail      str     — explanatory text
        url         str     — official VA URL

    Benefits are sorted by threshold ascending, then category, then name.
    If tdiu_eligible is True, the effective rating is treated as 100 for
    benefit lookup purposes (TDIU = paid at 100% rate).
    """
    effective_rating = 100 if tdiu_eligible else rating
    data = load_benefits_data()
    thresholds = data.get("thresholds", {})
    category_labels = data.get("category_labels", {})

    results = []
    for threshold_str, categories in thresholds.items():
        threshold = int(threshold_str)
        if threshold > effective_rating:
            continue
        for category_key, items in categories.items():
            label = category_labels.get(category_key, category_key.title())
            for item in items:
                results.append({
                    "threshold": threshold,
                    "category": category_key,
                    "category_label": label,
                    "name": item.get("name", ""),
                    "detail": item.get("detail", ""),
                    "url": item.get("url", ""),
                })

    results.sort(key=lambda x: (x["threshold"], x["category"], x["name"]))
    return results


def get_benefits_by_category(rating: int, tdiu_eligible: bool = False) -> dict[str, list[dict]]:
    """
    Same as get_benefits_for_rating but grouped by category_label for display.
    Returns an ordered dict: category_label -> [benefit, ...]
    """
    benefits = get_benefits_for_rating(rating, tdiu_eligible)
    grouped: dict[str, list[dict]] = {}
    for b in benefits:
        grouped.setdefault(b["category_label"], []).append(b)
    return grouped


# Convenience re-export so callers don't need to load the file themselves
def get_category_labels() -> dict[str, str]:
    return load_benefits_data().get("category_labels", {})
