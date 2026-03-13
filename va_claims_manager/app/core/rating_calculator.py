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


def check_tdiu_eligibility(individual_ratings: list[int]) -> dict:
    """
    Check TDIU (Total Disability based on Individual Unemployability) eligibility.

    Per 38 CFR § 4.16:
      - One disability rated at 60%+ (single disability schedular), OR
      - Combined rating 70%+ with at least one disability rated 40%+

    Args:
        individual_ratings: List of individual disability percentages.

    Returns:
        dict with: eligible (bool), reason (str), criteria_met (str | None)
    """
    if not individual_ratings:
        return {"eligible": False, "reason": "No disability ratings entered.", "criteria_met": None}

    clean = sorted([max(0, min(100, r)) for r in individual_ratings], reverse=True)
    max_single = clean[0]
    combined = combined_rating(clean)

    if max_single >= 60:
        return {
            "eligible": True,
            "reason": (
                f"Single disability at {max_single}% meets the 60% threshold for TDIU "
                f"(38 CFR § 4.16(a)).\n"
                f"File VA Form 21-8940 (Unemployability Application) and VA Form 21-4192 "
                f"(Employment Verification from last employer)."
            ),
            "criteria_met": "single_60",
        }

    if combined >= 70 and max_single >= 40:
        return {
            "eligible": True,
            "reason": (
                f"Combined rating {combined}% (≥70%) with primary disability at {max_single}% "
                f"(≥40%) meets multi-disability TDIU criteria (38 CFR § 4.16(a)).\n"
                f"File VA Form 21-8940 (Unemployability Application) and VA Form 21-4192 "
                f"(Employment Verification from last employer)."
            ),
            "criteria_met": "combined_70_40",
        }

    # Near-miss hints
    if max_single >= 40 and combined < 70:
        note = (
            f"Primary disability at {max_single}% qualifies as lead — need combined ≥70% "
            f"(currently {combined}%, need {70 - combined}% more)."
        )
    else:
        note = (
            f"TDIU not yet met. Need: one disability ≥60%, OR combined ≥70% with one ≥40%.\n"
            f"Currently: highest single = {max_single}%, combined = {combined}%."
        )

    return {"eligible": False, "reason": note, "criteria_met": None}


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
