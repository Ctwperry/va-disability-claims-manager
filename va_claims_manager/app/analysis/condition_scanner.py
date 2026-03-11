"""
Medical record condition scanner.

Searches a veteran's indexed documents for mentions of claimable VA disability
conditions.  Returns a ranked list of PotentialClaim objects with supporting
evidence snippets so the veteran can review and decide what to file.
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class ConditionEvidence:
    page_id: int
    page_number: int
    doc_name: str
    doc_type: str
    document_id: int
    snippet: str          # cleaned snippet text (no markup)
    matched_keyword: str  # which keyword triggered the match


@dataclass
class PotentialClaim:
    vasrd_code: str
    condition_name: str
    body_system: str
    evidence: list[ConditionEvidence] = field(default_factory=list)
    already_claimed: bool = False

    @property
    def evidence_count(self) -> int:
        return len(self.evidence)

    @property
    def confidence(self) -> str:
        n = self.evidence_count
        if n >= 5:
            return "High"
        elif n >= 2:
            return "Medium"
        return "Low"

    @property
    def confidence_color(self) -> str:
        return {"High": "#1a7a4a", "Medium": "#b8610a", "Low": "#555e6e"}[self.confidence]

    @property
    def confidence_bg(self) -> str:
        return {"High": "#e8f8f0", "Medium": "#fff3e0", "Low": "#f0f2f5"}[self.confidence]


# ---------------------------------------------------------------------------
# Keyword library
# Each entry maps a VASRD code to a list of search phrases.
# Multi-word phrases are searched as FTS5 phrase queries.
# Hyphens are stripped before building the query (FTS5 tokenizer splits them).
# ---------------------------------------------------------------------------

CONDITION_KEYWORDS: dict[str, list[str]] = {
    # ---- Musculoskeletal: Spine ----
    "5237": ["lumbosacral strain", "cervical strain", "lumbar strain", "back strain", "neck strain"],
    "5242": ["spondylosis", "degenerative arthritis spine", "degenerative disc",
             "osteophyte", "DDD", "disc disease"],
    "5243": ["intervertebral disc", "IVDS", "disc herniation", "herniated disc",
             "disc bulge", "disc protrusion", "annular tear"],
    "5238": ["spinal stenosis", "stenosis lumbar", "stenosis cervical",
             "neurogenic claudication", "canal stenosis"],
    "5241": ["spinal fusion", "lumbar fusion", "cervical fusion", "ACDF", "ALIF", "TLIF", "PLIF"],
    "5235": ["vertebral fracture", "compression fracture", "spinal fracture", "vertebral dislocation"],
    "5239": ["spondylolisthesis", "anterolisthesis", "retrolisthesis", "segmental instability"],
    "5295": ["chronic low back", "chronic lumbar", "low back pain", "LBP"],
    "5293": ["cervical disc", "cervical radiculopathy", "cervical myelopathy"],
    "5292": ["lumbar range of motion", "lumbar ROM", "spinal range of motion"],
    # ---- Musculoskeletal: Knee ----
    "5257": ["knee instability", "knee laxity", "medial collateral ligament",
             "lateral collateral ligament", "ACL tear", "PCL tear", "knee impairment"],
    "5258": ["meniscus tear", "meniscal tear", "semilunar cartilage", "meniscus damage"],
    "5259": ["meniscectomy", "meniscus removal", "partial meniscectomy"],
    "5260": ["knee flexion limited", "limitation of flexion knee"],
    "5261": ["knee extension limited", "limitation of extension knee"],
    "5055": ["total knee arthroplasty", "knee replacement", "TKA", "knee prosthesis"],
    # ---- Musculoskeletal: Hip ----
    "5151": ["total hip arthroplasty", "hip replacement", "THA", "hip prosthesis"],
    "5152": ["hip flexion limited", "hip limited motion"],
    # ---- Musculoskeletal: Shoulder ----
    "5201": ["rotator cuff", "shoulder impingement", "AC joint", "shoulder limitation",
             "shoulder ROM", "shoulder range of motion", "supraspinatus", "infraspinatus"],
    "5202": ["humerus fracture", "humeral fracture", "proximal humerus"],
    "5051": ["total shoulder arthroplasty", "shoulder replacement", "shoulder prosthesis"],
    # ---- Musculoskeletal: Ankle/Foot ----
    "5271": ["ankle dorsiflexion", "ankle plantar flexion", "ankle limited", "ankle sprain chronic"],
    "5276": ["pes planus", "flatfoot", "flat feet", "fallen arches", "plantar fascia"],
    "5284": ["foot injury", "metatarsal fracture", "foot fracture", "mid foot"],
    "5309": ["plantar fasciitis", "heel spur", "heel pain plantar"],
    # ---- Musculoskeletal: General ----
    "5003": ["osteoarthritis", "degenerative joint disease", "DJD", "joint degeneration",
             "joint arthritis", "wear arthritis"],
    "5002": ["rheumatoid arthritis", "RA joint", "polyarthritis", "rheumatoid factor"],
    "5025": ["fibromyalgia", "widespread pain", "tender points", "fibromyositis"],
    "5019": ["bursitis", "subacromial bursitis", "trochanteric bursitis", "olecranon bursitis",
             "prepatellar bursitis"],
    "5024": ["tenosynovitis", "tendinitis", "tendinopathy", "tendon inflammation", "tendon injury"],
    "5010": ["post traumatic arthritis", "traumatic arthritis", "arthritis due to trauma"],
    # ---- Mental Health ----
    "9411": ["PTSD", "post traumatic stress", "posttraumatic stress", "combat stress",
             "military sexual trauma", "MST", "hypervigilance", "intrusive thoughts",
             "nightmares trauma", "trauma survivor", "avoidance symptoms"],
    "9434": ["major depressive disorder", "major depression", "MDD", "depressive disorder",
             "depression diagnosis", "persistent depression"],
    "9432": ["bipolar disorder", "bipolar", "manic episode", "manic depressive", "bipolar I", "bipolar II"],
    "9400": ["generalized anxiety disorder", "GAD", "anxiety disorder", "chronic anxiety",
             "anxiety diagnosis"],
    "9440": ["adjustment disorder", "chronic adjustment disorder"],
    "9404": ["obsessive compulsive disorder", "OCD", "obsessional"],
    "9412": ["panic disorder", "panic attacks", "agoraphobia"],
    "9416": ["dysthymia", "persistent depressive disorder", "chronic depression"],
    "9201": ["schizophrenia", "paranoid schizophrenia", "schizophrenic"],
    "9210": ["schizoaffective disorder", "schizoaffective"],
    "9304": ["dementia due to trauma", "traumatic dementia", "cognitive decline trauma"],
    # ---- Sensory: Hearing ----
    "6260": ["tinnitus", "ringing in ears", "ringing ears", "bilateral tinnitus", "ear ringing"],
    "6100": ["sensorineural hearing loss", "noise induced hearing loss", "bilateral hearing loss",
             "NIHL", "audiogram", "hearing loss bilateral"],
    "6101": ["hearing loss right ear", "right sensorineural"],
    "6102": ["hearing loss left ear", "left sensorineural"],
    "6200": ["otitis media", "suppurative otitis", "middle ear infection chronic"],
    "6204": ["vestibular disorder", "vertigo chronic", "labyrinthitis", "vestibular dysfunction"],
    "6205": ["Meniere disease", "Meniere syndrome", "endolymphatic hydrops"],
    # ---- Sensory: Vision ----
    "6011": ["glaucoma", "elevated intraocular pressure", "IOP elevated", "optic nerve glaucoma"],
    "6053": ["traumatic cataract", "cataract trauma"],
    "6040": ["diabetic retinopathy", "retinal changes diabetes"],
    "6025": ["optic neuropathy", "optic nerve damage", "optic nerve injury"],
    "6026": ["traumatic optic neuropathy", "optic nerve trauma"],
    # ---- Respiratory ----
    "6847": ["sleep apnea", "obstructive sleep apnea", "OSA", "CPAP", "AHI",
             "polysomnography", "apnea hypopnea index"],
    "6602": ["bronchial asthma", "asthma diagnosis", "reactive airway disease",
             "bronchospasm", "albuterol inhaler", "asthmatic"],
    "6604": ["COPD", "chronic obstructive pulmonary disease", "emphysema",
             "spirometry obstruction", "FEV1 reduced"],
    "6845": ["chronic bronchitis", "bronchitis chronic", "productive cough chronic"],
    "6843": ["restrictive lung disease", "pulmonary restriction", "TLC reduced"],
    "6825": ["pulmonary fibrosis", "interstitial fibrosis", "ILD",
             "interstitial lung disease", "UIP"],
    "6801": ["sarcoidosis", "granulomatous lung disease", "pulmonary sarcoid"],
    "6841": ["allergic rhinitis", "rhinitis allergic", "hay fever chronic"],
    "6840": ["vasomotor rhinitis", "chronic rhinitis", "nasal obstruction chronic"],
    "6848": ["chronic sinusitis", "sinusitis chronic", "pansinusitis"],
    "6510": ["maxillary sinusitis", "chronic maxillary sinus"],
    "6511": ["frontal sinusitis", "chronic frontal sinus"],
    "6846": ["pulmonary hypertension", "PAH", "pulmonary arterial hypertension"],
    "6817": ["lung cancer", "carcinoma lung", "bronchogenic carcinoma", "NSCLC", "SCLC",
             "non small cell lung"],
    "6819": ["mesothelioma", "asbestos exposure", "pleural mesothelioma"],
    # ---- Cardiovascular ----
    "7101": ["hypertension", "high blood pressure", "HTN", "elevated blood pressure",
             "antihypertensive", "hypertensive"],
    "7005": ["coronary artery disease", "CAD", "ischemic heart disease", "angina",
             "arteriosclerotic heart"],
    "7006": ["myocardial infarction", "heart attack", "MI", "NSTEMI", "STEMI",
             "cardiac infarction"],
    "7022": ["congestive heart failure", "CHF", "heart failure", "cardiomegaly",
             "BNP elevated", "ejection fraction reduced"],
    "7118": ["atrial fibrillation", "AFib", "atrial flutter", "a fib"],
    "7119": ["cardiac arrhythmia", "dysrhythmia", "arrhythmia"],
    "7115": ["deep vein thrombosis", "DVT", "thrombophlebitis", "blood clot leg"],
    "7114": ["pulmonary embolism", "PE thromboembolism"],
    "7100": ["peripheral vascular disease", "PVD", "peripheral arterial disease",
             "PAD claudication"],
    "7122": ["cold injury residual", "frostbite injury", "trench foot"],
    "7007": ["hypertensive heart disease", "left ventricular hypertrophy", "LVH"],
    "7010": ["supraventricular tachycardia", "SVT", "paroxysmal SVT"],
    "7113": ["ventricular aneurysm"],
    "7112": ["pericarditis chronic"],
    # ---- Neurological ----
    "8045": ["traumatic brain injury", "TBI", "closed head injury", "concussion",
             "mTBI", "blast injury", "post concussion syndrome"],
    "8100": ["migraine headache", "migraine", "vascular headache", "chronic headache"],
    "8105": ["grand mal seizure", "generalized tonic clonic", "seizure disorder", "epilepsy"],
    "8113": ["post traumatic seizure", "post traumatic epilepsy"],
    "8510": ["cervical radiculopathy", "C spine radiculopathy",
             "upper extremity numbness radiculopathy"],
    "8512": ["lumbar radiculopathy", "L spine radiculopathy", "lower extremity radiculopathy",
             "sciatica diagnosis"],
    "8520": ["sciatic nerve paralysis", "foot drop sciatic"],
    "8521": ["sciatic neuritis"],
    "8522": ["sciatica", "sciatic neuralgia", "sciatic pain chronic"],
    "8004": ["Parkinson disease", "parkinsonism", "Parkinson tremor"],
    "8010": ["multiple sclerosis", "MS diagnosis", "demyelinating disease"],
    "8018": ["amyotrophic lateral sclerosis", "ALS", "Lou Gehrig disease"],
    "8214": ["Bell palsy", "facial nerve palsy", "CN VII palsy"],
    "8028": ["cerebral arteriosclerosis"],
    # ---- Skin ----
    "7800": ["significant scar", "scar tissue", "cicatrix"],
    "7801": ["burn scar", "burn injury scar"],
    "7804": ["unstable scar", "scar ulceration"],
    "7806": ["dermatitis", "eczema", "atopic dermatitis", "contact dermatitis"],
    "7816": ["psoriasis", "psoriatic dermatitis"],
    "7833": ["melanoma", "malignant melanoma"],
    "7829": ["chloracne", "dioxin exposure skin", "TCDD exposure"],
    # ---- Digestive ----
    "7205": ["GERD", "gastroesophageal reflux disease", "acid reflux chronic",
             "Barrett esophagus", "heartburn chronic"],
    "7304": ["peptic ulcer disease", "PUD", "peptic ulcer"],
    "7305": ["gastric ulcer"],
    "7306": ["duodenal ulcer"],
    "7307": ["gastritis chronic", "chronic gastritis", "H pylori gastritis"],
    "7321": ["Crohn disease", "Crohn's disease", "regional ileitis", "IBD Crohn"],
    "7322": ["ulcerative colitis", "inflammatory bowel disease", "UC colitis"],
    "7319": ["irritable bowel syndrome", "IBS", "spastic colon", "functional bowel"],
    "7312": ["cirrhosis", "liver cirrhosis", "hepatic cirrhosis"],
    "7316": ["hepatitis B chronic", "chronic hepatitis B", "HBV positive"],
    "7345": ["hepatitis C chronic", "chronic hepatitis C", "HCV positive"],
    "7338": ["inguinal hernia"],
    "7341": ["hiatal hernia", "hiatus hernia"],
    "7347": ["pancreatitis", "chronic pancreatitis", "pancreatic insufficiency"],
    "7309": ["gastric cancer", "stomach carcinoma", "adenocarcinoma stomach"],
    # ---- Genitourinary ----
    "7507": ["chronic kidney disease", "CKD", "renal failure chronic",
             "renal insufficiency", "creatinine elevated chronic"],
    "7502": ["pyelonephritis chronic", "kidney infection chronic"],
    "7504": ["nephrolithiasis", "kidney stones", "renal calculi"],
    "7515": ["interstitial cystitis", "chronic cystitis", "bladder inflammation chronic"],
    "7521": ["prostate cancer", "prostate carcinoma", "adenocarcinoma prostate"],
    "7527": ["benign prostatic hyperplasia", "BPH", "enlarged prostate", "prostatism"],
    "7522": ["erectile dysfunction", "impotence diagnosis"],
    "7530": ["urinary incontinence", "bladder incontinence chronic"],
    "7519": ["bladder cancer", "bladder carcinoma", "transitional cell carcinoma bladder"],
    # ---- Endocrine ----
    "7913": ["type 2 diabetes", "diabetes mellitus type 2", "T2DM",
             "non insulin dependent diabetes", "diabetes diagnosis"],
    "7911": ["type 1 diabetes", "diabetes mellitus type 1", "T1DM",
             "insulin dependent diabetes"],
    "7902": ["hypothyroidism", "underactive thyroid", "levothyroxine",
             "thyroid deficiency", "Hashimoto thyroiditis"],
    "7900": ["hyperthyroidism", "overactive thyroid", "Grave disease", "thyrotoxicosis"],
    "7915": ["thyroid cancer", "thyroid carcinoma", "papillary thyroid cancer"],
    "7907": ["Cushing syndrome", "hypercortisolism", "adrenal excess cortisol"],
    "7910": ["Addison disease", "adrenal insufficiency", "hypocortisolism"],
    # ---- Hematologic ----
    "7703": ["leukemia", "ALL leukemia", "AML leukemia", "CLL", "CML",
             "lymphocytic leukemia", "myelogenous leukemia"],
    "7709": ["Hodgkin lymphoma", "Hodgkin disease"],
    "7715": ["non Hodgkin lymphoma", "NHL diagnosis", "B cell lymphoma", "T cell lymphoma"],
    "7714": ["multiple myeloma", "plasma cell myeloma"],
    "7718": ["MGUS", "monoclonal gammopathy", "plasma cell dyscrasia"],
    "7721": ["immune thrombocytopenia", "ITP platelet", "thrombocytopenic purpura"],
    "7704": ["aplastic anemia"],
    # ---- Immune / Autoimmune ----
    "6351": ["systemic lupus erythematosus", "SLE", "lupus diagnosis"],
    "6355": ["chronic fatigue syndrome", "CFS", "ME CFS", "myalgic encephalomyelitis"],
    "6354": ["Gulf War illness", "Gulf War syndrome", "undiagnosed illness veteran",
             "medically unexplained chronic"],
    "6310": ["Lyme disease", "chronic Lyme", "borrelia infection"],
    "6319": ["HIV", "human immunodeficiency virus", "AIDS diagnosis"],
    # ---- PACT Act / Toxic Exposure ----
    "7920": ["burn pit exposure", "airborne hazards", "open burn pit"],
    "7932": ["glioblastoma", "brain cancer veteran", "brain tumor"],
    "7930": ["lymphatic cancer veteran", "lymphoma toxic exposure"],
    "7931": ["thyroid cancer radiation", "thyroid carcinoma veteran"],
}


# ---------------------------------------------------------------------------
# Scanner
# ---------------------------------------------------------------------------

def scan_veteran_records(
    veteran_id: int,
    existing_condition_names: set[str] | None = None,
    progress_cb: Callable[[int, int, str], None] | None = None,
) -> tuple[list[PotentialClaim], int, int]:
    """
    Scan all indexed documents for a veteran and identify potential disability conditions.

    Args:
        veteran_id: The veteran to scan.
        existing_condition_names: Set of condition names already claimed (to mark already_claimed).
        progress_cb: Optional callback(current, total, message).

    Returns:
        (potential_claims, total_docs, total_pages)
        potential_claims is sorted High → Medium → Low confidence, then by evidence count.
    """
    import app.db.connection as db_conn
    from app.config import VASRD_CODES_PATH

    conn = db_conn.get_connection()
    existing_condition_names = existing_condition_names or set()

    # Get stats
    row = conn.execute(
        "SELECT COUNT(*) as doc_count FROM documents WHERE veteran_id=? AND ingestion_status='complete'",
        (veteran_id,)
    ).fetchone()
    total_docs = row["doc_count"] if row else 0

    row = conn.execute(
        """SELECT COUNT(*) as pg_count FROM document_pages dp
           JOIN documents d ON dp.document_id = d.id
           WHERE d.veteran_id=?""",
        (veteran_id,)
    ).fetchone()
    total_pages = row["pg_count"] if row else 0

    if total_pages == 0:
        return [], total_docs, total_pages

    # Load all VASRD codes so we can also scan codes not in the keyword dict
    vasrd_codes: list[dict] = []
    try:
        with open(VASRD_CODES_PATH) as f:
            vasrd_codes = json.load(f).get("codes", [])
    except Exception:
        pass

    code_to_meta = {c["code"]: c for c in vasrd_codes}

    # Build list of (code, condition_name, body_system, keywords)
    scan_targets: list[tuple[str, str, str, list[str]]] = []
    seen_codes: set[str] = set()

    for code, kws in CONDITION_KEYWORDS.items():
        if code in seen_codes:
            continue
        seen_codes.add(code)
        meta = code_to_meta.get(code, {})
        name = meta.get("name", code)
        system = meta.get("system", "General")
        scan_targets.append((code, name, system, kws))

    # For any VASRD code NOT in keyword dict, use the condition name as the keyword
    for meta in vasrd_codes:
        code = meta["code"]
        if code not in seen_codes:
            seen_codes.add(code)
            kws = [meta["name"]]  # use full name as fallback phrase
            scan_targets.append((code, meta["name"], meta.get("system", "General"), kws))

    total = len(scan_targets)
    results: list[PotentialClaim] = []

    for idx, (code, name, system, keywords) in enumerate(scan_targets):
        if progress_cb:
            progress_cb(idx + 1, total, f"Checking: {name}...")

        evidence = _query_condition(conn, veteran_id, keywords)
        if not evidence:
            continue

        already = any(
            name.lower() in cn.lower() or cn.lower() in name.lower()
            for cn in existing_condition_names
        )
        claim = PotentialClaim(
            vasrd_code=code,
            condition_name=name,
            body_system=system,
            evidence=evidence,
            already_claimed=already,
        )
        results.append(claim)

    # Sort: High first, then by evidence count descending
    order = {"High": 0, "Medium": 1, "Low": 2}
    results.sort(key=lambda c: (order[c.confidence], -c.evidence_count))

    return results, total_docs, total_pages


def _query_condition(
    conn,
    veteran_id: int,
    keywords: list[str],
    max_results: int = 6,
) -> list[ConditionEvidence]:
    """Run an FTS5 search for a condition's keywords and return evidence."""
    fts_query = _build_fts_query(keywords)
    if not fts_query:
        return []

    SQL = """
        SELECT dp.id AS page_id,
               dp.page_number,
               dp.document_id,
               d.filename,
               d.doc_type,
               snippet(document_search, 0, '>>>',  '<<<', ' ... ', 28) AS raw_snippet
        FROM document_search
        JOIN document_pages dp ON document_search.rowid = dp.id
        JOIN documents d ON dp.document_id = d.id
        WHERE document_search MATCH ?
          AND d.veteran_id = ?
          AND d.ingestion_status = 'complete'
        ORDER BY rank
        LIMIT ?
    """
    try:
        rows = conn.execute(SQL, (fts_query, veteran_id, max_results)).fetchall()
    except Exception as exc:
        log.debug("FTS5 query failed for %r: %s", fts_query, exc)
        return []

    evidence = []
    seen_pages: set[int] = set()
    for row in rows:
        if row["page_id"] in seen_pages:
            continue
        seen_pages.add(row["page_id"])
        # Find which keyword matched (heuristic: check raw snippet)
        matched_kw = _find_matched_keyword(keywords, row["raw_snippet"])
        snippet = _clean_snippet(row["raw_snippet"])
        evidence.append(ConditionEvidence(
            page_id=row["page_id"],
            page_number=row["page_number"],
            doc_name=row["filename"],
            doc_type=row["doc_type"],
            document_id=row["document_id"],
            snippet=snippet,
            matched_keyword=matched_kw,
        ))
    return evidence


def _build_fts_query(keywords: list[str]) -> str:
    """Convert keyword list to FTS5 OR query with phrase quoting."""
    parts = []
    for kw in keywords:
        # Strip hyphens (FTS5 tokenizer splits on them anyway)
        normalized = kw.replace("-", " ").strip()
        if not normalized:
            continue
        # Quote as phrase query
        parts.append(f'"{normalized}"')
    return " OR ".join(parts)


def _find_matched_keyword(keywords: list[str], snippet: str) -> str:
    """Return the first keyword that appears (case-insensitive) in the snippet."""
    snippet_lower = snippet.lower()
    for kw in keywords:
        if kw.lower().replace("-", " ") in snippet_lower:
            return kw
    return keywords[0] if keywords else ""


def _clean_snippet(raw: str) -> str:
    """Remove FTS5 markers and clean whitespace from a snippet."""
    text = raw.replace(">>>", "").replace("<<<", "")
    text = re.sub(r"\s+", " ", text).strip()
    return text
