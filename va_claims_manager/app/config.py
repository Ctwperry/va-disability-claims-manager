"""
Application-wide configuration: paths, constants, and settings.
"""
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

if getattr(sys, "frozen", False):
    # Running as a PyInstaller bundle
    APP_DIR = Path(sys.executable).parent
else:
    APP_DIR = Path(__file__).parent.parent

DATA_DIR = APP_DIR / "data"
DB_PATH = DATA_DIR / "va_claims.db"
EXPORTS_DIR = DATA_DIR / "exports"
FORMS_DIR = DATA_DIR / "forms"
FORM_TEMPLATES_DIR = FORMS_DIR / "templates"
VASRD_CODES_PATH = DATA_DIR / "vasrd_codes.json"
PACT_ACT_PATH = DATA_DIR / "pact_act_conditions.json"
BENEFITS_DATA_PATH = DATA_DIR / "benefits_data.json"

# ---------------------------------------------------------------------------
# Database encryption (SQLCipher + OS keychain)
# ---------------------------------------------------------------------------

KEYCHAIN_SERVICE = "va-claims-manager"
KEYCHAIN_ACCOUNT = "db-encryption-key"

# Ensure data directories exist at import time
for _dir in (DATA_DIR, EXPORTS_DIR, FORMS_DIR, FORM_TEMPLATES_DIR):
    _dir.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Application metadata
# ---------------------------------------------------------------------------

APP_NAME = "VA Disability Claims Manager"
APP_VERSION = "1.0.0"
WINDOW_TITLE = f"{APP_NAME} v{APP_VERSION}"

# ---------------------------------------------------------------------------
# Tesseract default paths (Windows)
# ---------------------------------------------------------------------------

TESSERACT_DEFAULT_PATHS = [
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    str(Path.home() / "AppData" / "Local" / "Programs" / "Tesseract-OCR" / "tesseract.exe"),
]

# ---------------------------------------------------------------------------
# Document types
# ---------------------------------------------------------------------------

DOC_TYPES = {
    "DD214": "DD-214 (Report of Separation)",
    "STR": "Service Treatment Record",
    "DBQ": "Disability Benefits Questionnaire (DBQ)",
    "NexusLetter": "Nexus Letter",
    "SupportStatement": "Statement in Support of Claim (21-4138)",
    "BuddyStatement": "Lay/Witness Statement (21-10210)",
    "VADecision": "VA Rating Decision",
    "PrivateMedical": "Private Medical Record",
    "VAMedical": "VA Medical Record",
    "SeparationAssessment": "Separation Health Assessment",
    "VocationalReport": "Vocational Expert Report",
    "Other": "Other Document",
}

DOC_TYPE_LABELS = list(DOC_TYPES.values())
DOC_TYPE_KEYS = list(DOC_TYPES.keys())

# ---------------------------------------------------------------------------
# VA Form definitions
# ---------------------------------------------------------------------------

VA_FORMS = {
    "21-526EZ": "Application for Disability Compensation and Related Compensation Benefits",
    "21-4138": "Statement in Support of Claim",
    "21-10210": "Lay/Witness Statement",
    "21-8940": "Veteran's Application for Increased Compensation Based on Unemployability (TDIU)",
    "21-4192": "Request for Employment Information in Connection with Claim for Disability Benefits",
    "DBQ-5003": "DBQ: Degenerative Arthritis and/or Osteoarthritis",
    "DBQ-5242": "DBQ: Spine (Cervical/Thoracolumbar)",
    "DBQ-6260": "DBQ: Tinnitus",
    "DBQ-6100": "DBQ: Hearing Loss and Tinnitus",
    "DBQ-9411": "DBQ: PTSD",
    "DBQ-6847": "DBQ: Sleep Apnea Syndromes",
    "DBQ-7101": "DBQ: Hypertension",
}

# ---------------------------------------------------------------------------
# Claim types
# ---------------------------------------------------------------------------

CLAIM_TYPES = {
    "direct": "Direct Service Connection",
    "secondary": "Secondary Service Connection",
    "aggravation": "Aggravation of Pre-Existing Condition",
    "presumptive": "Presumptive Service Connection",
    "increased": "Increased Rating (Already Rated)",
}

# ---------------------------------------------------------------------------
# Service eras (for PACT Act / Agent Orange eligibility)
# ---------------------------------------------------------------------------

SERVICE_ERAS = [
    "WWII (1941-1946)",
    "Korea (1950-1955)",
    "Vietnam (1964-1975)",
    "Cold War (1947-1991)",
    "Gulf War (1990-present)",
    "Post-9/11 (Sep 2001-present)",
    "Other",
]

MILITARY_BRANCHES = [
    "Army",
    "Navy",
    "Marine Corps",
    "Air Force",
    "Coast Guard",
    "Space Force",
    "Army National Guard",
    "Air National Guard",
    "Army Reserve",
    "Naval Reserve",
    "Marine Corps Reserve",
    "Air Force Reserve",
    "Coast Guard Reserve",
]

DISCHARGE_TYPES = [
    "Honorable",
    "General (Under Honorable Conditions)",
    "Other Than Honorable (OTH)",
    "Bad Conduct",
    "Dishonorable",
    "Uncharacterized",
]

BODY_SYSTEMS = [
    "Musculoskeletal",
    "Mental Health",
    "Respiratory",
    "Cardiovascular",
    "Neurological",
    "Sensory (Vision/Hearing)",
    "Digestive",
    "Genitourinary",
    "Endocrine",
    "Hematologic/Lymphatic",
    "Skin",
    "Infectious Disease",
    "Oncology/Cancer",
    "Other",
]

# ---------------------------------------------------------------------------
# Document type quality weights for evidence scoring
# Higher = more authoritative source.  Used by condition_scanner.py to
# compute weighted confidence scores instead of raw match counts.
# ---------------------------------------------------------------------------

DOC_TYPE_WEIGHTS: dict[str, float] = {
    "DBQ":                  1.0,  # Disability Benefits Questionnaire = C&P exam
    "NexusLetter":          1.0,  # Specialist nexus opinion
    "STR":                  0.9,  # Service Treatment Records
    "SeparationAssessment": 0.9,  # Thorough medical evaluation at separation
    "PrivateMedical":       0.85, # Private specialist / clinic records
    "VAMedical":            0.80, # VA medical records (primary care, clinic)
    "DD214":                0.70, # Separation document — mentions conditions
    "VADecision":           0.70, # Rating decision — objective but administrative
    "VocationalReport":     0.60, # Vocational expert report
    "SupportStatement":     0.40, # Veteran self-report (21-4138)
    "BuddyStatement":       0.40, # Lay / witness statement (21-10210)
    "Other":                0.50, # Unknown / uncategorized
}

# ---------------------------------------------------------------------------
# OCR minimum character threshold per page
# (If pdfplumber returns fewer chars, fall back to OCR)
# ---------------------------------------------------------------------------

OCR_FALLBACK_THRESHOLD = 50

# ---------------------------------------------------------------------------
# FTS5 search result limit
# ---------------------------------------------------------------------------

SEARCH_RESULT_LIMIT = 500
SEARCH_SNIPPET_WORDS = 32
