"""
VA Combined Disability Rating Calculator.

The VA does NOT simply add disability percentages. It uses the "whole person"
method: each disability is applied to the remaining "healthy" portion.

Example: 50% + 30%
  Whole person remaining after 50% = 50%
  30% of 50 = 15%
  Combined = 50 + 15 = 65% → rounds to 70% (nearest 10)
"""


def combined_rating(ratings: list[int]) -> int:
    """
    Calculate the VA combined disability rating.

    Args:
        ratings: List of individual disability percentages (0-100).

    Returns:
        Final combined rating rounded to nearest 10% increment.
    """
    if not ratings:
        return 0

    # Sort descending for consistent calculation
    sorted_ratings = sorted([max(0, min(100, r)) for r in ratings], reverse=True)

    remaining = 100.0
    for rating in sorted_ratings:
        disability = remaining * (rating / 100.0)
        remaining -= disability

    combined = round(100.0 - remaining)

    # Round to nearest 10
    return _round_to_nearest_10(combined)


def bilateral_adjustment(ratings: list[int]) -> int:
    """
    Apply the bilateral factor: when both sides of the body are affected,
    add 10% of the combined bilateral rating to the total.

    Args:
        ratings: Combined rating of the bilateral disabilities only.

    Returns:
        Adjustment value (typically a small number to add).
    """
    if not ratings:
        return 0
    base = combined_rating(ratings)
    return round(base * 0.10)


def _round_to_nearest_10(value: float) -> int:
    """Round a VA combined rating to the nearest 10% increment (VA convention)."""
    # VA rounds 5 up (e.g., 55% → 60%, 54% → 50%)
    return int((value + 5) // 10) * 10


def rating_summary(ratings: list[int]) -> dict:
    """
    Return a human-readable summary of the combined rating calculation.
    """
    if not ratings:
        return {"combined": 0, "steps": [], "note": "No ratings provided"}

    sorted_ratings = sorted([max(0, min(100, r)) for r in ratings], reverse=True)
    steps = []
    remaining = 100.0

    for i, rating in enumerate(sorted_ratings):
        disability = remaining * (rating / 100.0)
        steps.append({
            "rating": rating,
            "remaining_before": round(remaining, 1),
            "disability_applied": round(disability, 1),
            "remaining_after": round(remaining - disability, 1),
        })
        remaining -= disability

    raw_combined = round(100.0 - remaining)
    final = _round_to_nearest_10(raw_combined)

    return {
        "individual_ratings": sorted_ratings,
        "raw_combined": raw_combined,
        "combined": final,
        "steps": steps,
        "note": f"Raw: {raw_combined}% → Rounded to nearest 10: {final}%",
    }
