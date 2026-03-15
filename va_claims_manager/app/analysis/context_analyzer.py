"""
Linguistic context analysis for medical record keyword matches.

Given the text window surrounding a keyword match, classifies it as:
  - Positive Diagnosis  (confirmed, active, being treated)
  - Negation            (denied, ruled out, negative test)
  - Workup/Differential (being evaluated, rule-out differential)
  - Family History      (relative's condition, not the veteran's)
  - Resolved            (past, healed, in remission)
  - Uncertain           (possible, questionable, suspected)
  - Mentioned           (bare mention, no strong signal)

Public API:
    analyze_context(context: str) -> ContextAnalysis
"""
from __future__ import annotations

import re
from dataclasses import dataclass


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class ContextAnalysis:
    negation_detected: bool = False   # "denies", "ruled out", "no evidence of"
    positive_diagnosis: bool = False  # "diagnosed with", "assessment:", "on treatment for"
    uncertainty_flag: bool = False    # "possible", "questionable", "suspected"
    family_history: bool = False      # "family history of", "father had"
    resolved: bool = False            # "resolved", "healed", "in remission"
    pattern_label: str = ""           # Human-readable: "Positive Diagnosis", "Negation", …
    pattern_icon: str = ""            # "✓", "⚠", "~", "·"


# ---------------------------------------------------------------------------
# Pattern banks  (compiled once at import time)
# ---------------------------------------------------------------------------

def _compile(*patterns: str) -> list[re.Pattern]:
    return [re.compile(p, re.IGNORECASE) for p in patterns]


_FAMILY_HISTORY = _compile(
    r"\bfamily\s+history\s+of\b",
    r"\bfamily\s+hx\s+of\b",
    r"\bFHx\b",
    r"\bfather\s+(?:had|has|with)\b",
    r"\bmother\s+(?:had|has|with)\b",
    r"\bparent(?:s)?\s+(?:had|has|with)\b",
    r"\bsibling(?:s)?\s+(?:had|has|with)\b",
    r"\bgrandfather\s+(?:had|has)\b",
    r"\bgrandmother\s+(?:had|has)\b",
    r"\bgenetic\s+predisposition\b",
    r"\bheritable\b",
)

_NEGATION = _compile(
    r"\bdenies?\b",
    r"\bdenied\b",
    r"\bno\s+evidence\s+of\b",
    r"\bno\s+signs?\s+of\b",
    r"\bno\s+symptoms?\s+of\b",
    r"\bwithout\s+(?:signs?|evidence|symptoms?)\s+of\b",
    r"\bruled?\s+out\b",
    r"\bR/?O\b",                            # "R/O", "RO" in notes
    r"\bnegative\s+for\b",
    r"\btest(?:ed)?\s+negative\b",
    r"\bresult(?:s)?\s+negative\b",
    r"\bnot\s+present\b",
    r"\bnot\s+consistent\s+with\b",
    r"\bnot\s+diagnosed\b",
    r"\bdoes\s+not\s+have\b",
    r"\bdoes\s+not\s+meet\s+criteria\b",
    r"\babsent\b",
    r"\bunremarkable\s+for\b",
    r"\bno\s+\w+\s+noted\b",               # "no X noted"
    r"\bno\s+active\b",
    r"\bnot\s+found\b",
    r"\bnot\s+identified\b",
    r"\bexcluded\b",
)

_WORKUP = _compile(
    r"\bworkup\s+for\b",
    r"\bconsider(?:ing)?\b",
    r"\bdifferential\s+(?:diagnosis|dx|diagnos[ei]s)?\b",
    r"\bto\s+rule\s+out\b",
    r"\bscreen(?:ing|ed)?\s+for\b",
    r"\bevaluat(?:e|ing|ed)\s+for\b",
    r"\binvestigat(?:e|ing|ed)\s+for\b",
    r"\bwork(?:up|ing)\s+up\b",
)

_RESOLVED = _compile(
    r"\bresolved\b",
    r"\bhealed\b",
    r"\bremitted\b",
    r"\bno\s+longer\b",
    r"\bin\s+remission\b",
    r"\bprevious(?:ly)?\s+(?:had|diagnosed|treated)\b",
    r"\bhistory\s+of\s+\w[\w\s]{0,40}(?:resolved|healed|remitted)\b",
)

_POSITIVE = _compile(
    r"\bdiagnosed\s+with\b",
    r"\bdiagnosis\s*:",
    r"\bdiagnosis\s+of\b",
    r"\bassessment\s*:",
    r"\bimpression\s*:",
    r"\bplan\s*:",
    r"\bsuffers?\s+from\b",
    r"\bpatient\s+(?:has|is)\b",
    r"\bpresents?\s+with\b",
    r"\bcomplains?\s+of\b",
    r"\bcurrently\s+taking\b",
    r"\bon\s+(?:treatment|therapy|medication)\s+for\b",
    r"\bfollows?\s+for\b",
    r"\bconsistent\s+with\b",
    r"\bclinically\s+significant\b",
    r"\bconfirmed\b",
    r"\bactive\s+\w",
    r"\bchronic\s+\w",
    r"\bprescribed\b",
    r"\breferred\s+for\b",
    r"\btreated\s+for\b",
    r"\bknown\s+(?:history|diagnosis)\s+of\b",
    r"\bestablished\s+(?:diagnosis|condition)\b",
    r"\bstable\s+\w",                       # "stable X" = actively managed
    r"\bmanaged\s+with\b",
    r"\bmedication\s+for\b",
    r"\b(?:continues?|continuing)\s+to\b",
    r"\bfollow[- ]up\s+for\b",
    r"\bundergoing\s+treatment\b",
    r"\bservice.?connected\b",
    r"\bservice\s+connection\b",
    r"\bC&?P\s+exam(?:ination)?\b",
    r"\bDBQ\b",
    r"\brating\s+of\b",
)

_UNCERTAINTY = _compile(
    r"\bprobable\b",
    r"\bpossible\b",
    r"\bquestionable\b",
    r"\bmaybe\b",
    r"\bmay\s+have\b",
    r"\bsuspect(?:ed)?\b",
    r"\bsuspicious\s+(?:for|of)\b",
    r"\blikely\b",
    r"\bpresumptive\b",
    r"\bunconfirmed\b",
    r"\bpending\s+(?:workup|evaluation|confirmation|results?)\b",
    r"\bcannot\s+rule\s+out\b",
    r"\bnot\s+(?:yet\s+)?confirmed\b",
)


# ---------------------------------------------------------------------------
# Public function
# ---------------------------------------------------------------------------

def analyze_context(context: str) -> ContextAnalysis:
    """
    Classify the context window around a keyword match.

    Checks patterns in priority order:
      1. Family history  → strong exclusion, return immediately
      2. Negation / Workup
      3. Positive diagnosis
      4. Resolved status
      5. Uncertainty

    A single context may carry both 'resolved' and 'positive' signals
    (e.g., "resolved in 2010 but now recurrent").  Both flags are set;
    the scanner uses source_weight and the flags to compute a score.
    """
    result = ContextAnalysis()

    # 1. Family history — high priority exclusion
    if any(p.search(context) for p in _FAMILY_HISTORY):
        result.family_history = True
        result.pattern_label = "Family History"
        result.pattern_icon = "⚠"
        return result

    # 2. Negation
    has_negation = any(p.search(context) for p in _NEGATION)
    has_workup   = any(p.search(context) for p in _WORKUP)

    if has_negation:
        result.negation_detected = True
        result.pattern_label = "Negation"
        result.pattern_icon = "⚠"
    elif has_workup:
        result.negation_detected = True   # treat workup same as negation for scoring
        result.pattern_label = "Workup / Differential"
        result.pattern_icon = "⚠"

    # 3. Positive diagnosis (only set if no negation)
    if not result.negation_detected:
        if any(p.search(context) for p in _POSITIVE):
            result.positive_diagnosis = True
            result.pattern_label = "Positive Diagnosis"
            result.pattern_icon = "✓"

    # 4. Resolved — doesn't override negation/positive, adds flag
    if any(p.search(context) for p in _RESOLVED):
        result.resolved = True
        if not result.pattern_label:
            result.pattern_label = "Resolved / Past"
            result.pattern_icon = "~"

    # 5. Uncertainty modifier
    if any(p.search(context) for p in _UNCERTAINTY):
        result.uncertainty_flag = True
        if not result.pattern_label:
            result.pattern_label = "Uncertain"
            result.pattern_icon = "~"

    # Default
    if not result.pattern_label:
        result.pattern_label = "Mentioned"
        result.pattern_icon = "·"

    return result
