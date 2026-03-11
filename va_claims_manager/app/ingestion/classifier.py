"""
Heuristic document type classifier.
Examines the first 1500 characters of extracted text to assign a doc_type.
"""

_RULES: list[tuple[list[str], str]] = [
    # Highest priority — specific government forms
    (["dd form 214", "certificate of release or discharge", "report of separation"], "DD214"),
    (["separation health assessment", "sha-", "pre-separation"], "SeparationAssessment"),
    (["disability benefits questionnaire", "dbq", "va form 21-0781", "va form 10-0103"], "DBQ"),
    (["lay or witness statement", "21-10210", "10210"], "BuddyStatement"),
    (["statement in support of claim", "21-4138", "4138"], "SupportStatement"),
    (["unemployability", "21-8940", "8940", "individual unemployability", "tdiu"], "VAForm8940"),
    (["rating decision", "regional office", "service connection is", "combined rating"], "VADecision"),
    # Nexus / medical opinion
    (["nexus", "at least as likely as not", "medical nexus", "nexus letter", "medical opinion"], "NexusLetter"),
    # VA medical records
    (["veterans health administration", "vha", "va medical center", "vamc", "cprs", "ahlta",
      "jvh", "va outpatient", "dept. of veterans"], "VAMedical"),
    # Service treatment records
    (["service treatment record", "ahlta", "chcs", "in-service", "military treatment",
      "tricare", "military hospital", "active duty medical"], "STR"),
    # Vocational
    (["vocational expert", "labor market", "gainful employment", "occupational analysis"], "VocationalReport"),
]

_PRIVATE_KEYWORDS = [
    "medical record", "discharge summary", "clinic note", "progress note",
    "consultation", "radiology", "mri", "x-ray", "ct scan", "laboratory",
    "diagnosis", "treatment plan", "physician", "doctor", "hospital",
    "orthopedic", "neurologist", "psychiatrist", "psychologist",
]


def classify(text: str) -> str:
    """
    Return the best-match doc_type string for the given text sample.
    Caller should pass the first ~1500 characters of the document.
    """
    sample = text[:1500].lower()

    for keywords, doc_type in _RULES:
        if any(kw in sample for kw in keywords):
            return doc_type

    # Check for generic private medical evidence
    private_hits = sum(1 for kw in _PRIVATE_KEYWORDS if kw in sample)
    if private_hits >= 2:
        return "PrivateMedical"

    return "Other"


def extract_date_hint(text: str) -> str:
    """
    Try to extract the most prominent date from the first 500 characters.
    Returns ISO-8601 string or empty string.
    """
    import re
    sample = text[:500]

    # Match patterns: MM/DD/YYYY, YYYY-MM-DD, Month DD YYYY
    patterns = [
        r"\b(\d{4})-(\d{2})-(\d{2})\b",                       # YYYY-MM-DD
        r"\b(\d{1,2})[/\-](\d{1,2})[/\-](\d{4})\b",           # MM/DD/YYYY
        r"\b(january|february|march|april|may|june|july|august|"
        r"september|october|november|december)\s+(\d{1,2})[,\s]+(\d{4})\b",
    ]

    months = {
        "january": "01", "february": "02", "march": "03", "april": "04",
        "may": "05", "june": "06", "july": "07", "august": "08",
        "september": "09", "october": "10", "november": "11", "december": "12",
    }

    for pattern in patterns:
        m = re.search(pattern, sample, re.IGNORECASE)
        if m:
            groups = m.groups()
            if len(groups) == 3:
                a, b, c = groups
                # ISO format
                if re.match(r"\d{4}", a):
                    return f"{a}-{b}-{c}"
                # Month name
                elif a.lower() in months:
                    return f"{c}-{months[a.lower()]}-{int(b):02d}"
                # MM/DD/YYYY
                else:
                    try:
                        return f"{c}-{int(a):02d}-{int(b):02d}"
                    except ValueError:
                        pass
    return ""


def extract_author_hint(text: str) -> str:
    """Try to find a provider name in the first 500 chars."""
    import re
    sample = text[:500]
    # Look for "Dr. Lastname" or "M.D." / "D.O." nearby
    m = re.search(r"\bDr\.?\s+([A-Z][a-z]+(?: [A-Z][a-z]+)?)", sample)
    if m:
        return m.group(0)
    m = re.search(r"([A-Z][a-z]+(?: [A-Z]\.?)? [A-Z][a-z]+),?\s+(?:M\.D\.|D\.O\.|NP|PA-C|LCSW)", sample)
    if m:
        return m.group(0)
    return ""


def extract_facility_hint(text: str) -> str:
    """Try to find a facility name."""
    import re
    sample = text[:600]
    m = re.search(
        r"((?:VA|Veterans Affairs|Department of Veterans|"
        r"[A-Z][a-z]+(?: [A-Z][a-z]+)* (?:Hospital|Medical Center|Clinic|"
        r"Health System|Healthcare System)))",
        sample,
    )
    if m:
        return m.group(1)[:120]
    return ""
