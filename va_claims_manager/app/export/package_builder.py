"""
Claim package assembler.
Produces a structured folder with organized documents, claim summaries,
and pre-filled VA form references.
"""
import json
import logging
import shutil
from datetime import datetime
from pathlib import Path
from typing import Callable

log = logging.getLogger(__name__)


def build_package(
    veteran_id: int,
    output_dir: Path,
    claim_ids: list[int] | None = None,
    progress_cb: Callable[[int, int, str], None] | None = None,
) -> Path:
    """
    Build a complete claim package for a veteran.

    Args:
        veteran_id: The veteran to export.
        output_dir: Root directory for the package (will create subfolder).
        claim_ids: Optional list of specific claim IDs (None = all claims).
        progress_cb: Optional progress callback(current, total, message).

    Returns:
        Path to the created package folder.
    """
    import app.db.repositories.veteran_repo as veteran_repo
    import app.db.repositories.claim_repo as claim_repo
    import app.db.repositories.document_repo as doc_repo

    veteran = veteran_repo.get_by_id(veteran_id)
    if not veteran:
        raise ValueError(f"Veteran {veteran_id} not found")

    # Create timestamped package folder
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name = "".join(c if c.isalnum() or c in "_- " else "_" for c in veteran.full_name)
    package_dir = output_dir / f"{safe_name}_{timestamp}"
    package_dir.mkdir(parents=True, exist_ok=True)

    # Gather data
    all_claims = claim_repo.get_all(veteran_id)
    if claim_ids:
        claims = [c for c in all_claims if c.id in claim_ids]
    else:
        claims = all_claims

    all_docs = doc_repo.get_all(veteran_id)
    total_steps = 4 + len(claims) + 2
    step = 0

    def prog(msg):
        nonlocal step
        step += 1
        if progress_cb:
            progress_cb(step, total_steps, msg)

    # ---- 00_Cover_Sheet ----
    prog("Creating cover sheet...")
    cover_path = package_dir / "00_Cover_Sheet.pdf"
    try:
        from app.export.pdf_writer import write_cover_sheet_pdf
        write_cover_sheet_pdf(cover_path, veteran, claims, all_docs)
    except Exception as exc:
        log.warning("PDF cover sheet failed (%s) — writing plain-text fallback", exc)
        _write_cover_sheet(package_dir / "00_Cover_Sheet.txt", veteran, claims, all_docs)

    # ---- 01_DD214 ----
    prog("Copying DD-214...")
    dd214_docs = [d for d in all_docs if d.doc_type == "DD214"]
    if dd214_docs:
        dd214_dir = package_dir / "01_DD214"
        dd214_dir.mkdir(exist_ok=True)
        for doc in dd214_docs:
            _copy_doc(doc, dd214_dir)

    # ---- 02_ServiceTreatmentRecords ----
    prog("Copying service treatment records...")
    str_docs = [d for d in all_docs if d.doc_type == "STR"]
    if str_docs:
        str_dir = package_dir / "02_ServiceTreatmentRecords"
        str_dir.mkdir(exist_ok=True)
        for doc in str_docs:
            _copy_doc(doc, str_dir)

    # ---- 03_Claims ----
    claims_root = package_dir / "03_Claims"
    claims_root.mkdir(exist_ok=True)

    for claim in claims:
        prog(f"Packaging claim: {claim.condition_name}...")
        safe_condition = "".join(
            c if c.isalnum() or c in "_- " else "_" for c in claim.condition_name
        )
        code_suffix = f"_DC{claim.vasrd_code}" if claim.vasrd_code else ""
        claim_dir = claims_root / f"{safe_condition}{code_suffix}"
        claim_dir.mkdir(exist_ok=True)

        # Claim summary — PDF with text fallback
        try:
            from app.export.pdf_writer import write_claim_summary_pdf
            write_claim_summary_pdf(claim_dir / "Claim_Summary.pdf", claim, veteran)
        except Exception as exc:
            log.warning("PDF claim summary failed (%s) — writing plain-text fallback", exc)
            _write_claim_summary(claim_dir / "Claim_Summary.txt", claim, veteran)

        # Copy linked documents by role
        import app.db.connection as db_conn
        conn = db_conn.get_connection()
        links = conn.execute(
            "SELECT document_id, role FROM claim_documents WHERE claim_id=?", (claim.id,)
        ).fetchall()

        for link in links:
            doc = doc_repo.get_by_id(link["document_id"])
            if not doc:
                continue
            role = link["role"] or "supporting"
            role_dir = claim_dir / _role_to_folder(role)
            role_dir.mkdir(exist_ok=True)
            _copy_doc(doc, role_dir)

    # ---- 04_Forms ----
    prog("Generating form reference sheet...")
    forms_dir = package_dir / "04_Forms"
    forms_dir.mkdir(exist_ok=True)
    try:
        from app.export.pdf_writer import write_forms_checklist_pdf
        write_forms_checklist_pdf(forms_dir / "Required_Forms_Checklist.pdf", veteran, claims)
    except Exception as exc:
        log.warning("PDF forms checklist failed (%s) — writing plain-text fallback", exc)
        _write_forms_checklist(forms_dir / "Required_Forms_Checklist.txt", veteran, claims)

    # ---- 05_BuddyStatements ----
    prog("Copying buddy statements...")
    buddy_docs = [d for d in all_docs if d.doc_type in ("BuddyStatement", "SupportStatement")]
    if buddy_docs:
        buddy_dir = package_dir / "05_Buddy_Statements"
        buddy_dir.mkdir(exist_ok=True)
        for doc in buddy_docs:
            _copy_doc(doc, buddy_dir)

    # ---- 06_OtherDocuments ----
    other_docs = [d for d in all_docs if d.doc_type in ("PrivateMedical", "VAMedical", "Other")]
    if other_docs:
        prog("Copying other medical records...")
        other_dir = package_dir / "06_Other_Medical_Records"
        other_dir.mkdir(exist_ok=True)
        for doc in other_docs:
            _copy_doc(doc, other_dir)

    log.info("Package built at: %s", package_dir)
    return package_dir


# ---------------------------------------------------------------------------
# Writers
# ---------------------------------------------------------------------------

def _write_cover_sheet(path: Path, veteran, claims, docs):
    from app.core.rating_calculator import combined_rating
    lines = [
        "=" * 70,
        "VA DISABILITY CLAIMS PACKAGE",
        "=" * 70,
        "",
        "VETERAN INFORMATION",
        "-" * 40,
        f"Name:             {veteran.full_name}",
        f"Branch:           {veteran.branch}",
        f"Service Era:      {veteran.era}",
        f"Service Dates:    {veteran.entry_date} to {veteran.separation_date}",
        f"Discharge Type:   {veteran.discharge_type}",
        f"DD-214 on file:   {'Yes' if veteran.dd214_on_file else 'No'}",
        "",
        "CLAIMS SUMMARY",
        "-" * 40,
    ]

    ratings = [c.priority_rating for c in claims if c.priority_rating]
    if ratings:
        est_combined = combined_rating(ratings)
        lines.append(f"Estimated Combined Rating: {est_combined}%")
    lines.append(f"Total Claims: {len(claims)}")
    complete = sum(1 for c in claims if c.triangle_complete)
    lines.append(f"Triangle Complete: {complete}/{len(claims)}")
    lines.append("")

    for i, claim in enumerate(claims, 1):
        legs = (
            f"[{'✓' if claim.has_diagnosis else '✗'}]Dx "
            f"[{'✓' if claim.has_inservice_event else '✗'}]InSvc "
            f"[{'✓' if claim.has_nexus else '✗'}]Nexus"
        )
        risks = f" | {claim.risk_count} risk(s)" if claim.risk_count else ""
        rating_str = f" | Est: {claim.priority_rating}%" if claim.priority_rating else ""
        lines.append(f"  {i}. {claim.condition_name} {claim.vasrd_code or ''}")
        lines.append(f"     {legs}{risks}{rating_str}")

    lines += [
        "",
        "DOCUMENT INVENTORY",
        "-" * 40,
        f"Total documents: {len(docs)}",
        f"Total pages:     {sum(d.page_count for d in docs):,}",
        "",
    ]

    from app.config import DOC_TYPES
    from collections import Counter
    type_counts = Counter(d.doc_type for d in docs)
    for doc_type, count in sorted(type_counts.items()):
        label = DOC_TYPES.get(doc_type, doc_type)
        lines.append(f"  {label}: {count}")

    lines += [
        "",
        "=" * 70,
        f"Package generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "=" * 70,
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def _write_claim_summary(path: Path, claim, veteran):
    from app.config import CLAIM_TYPES
    lines = [
        "=" * 60,
        f"CLAIM SUMMARY: {claim.condition_name}",
        "=" * 60,
        "",
        f"VASRD Code:   {claim.vasrd_code or 'Not specified'}",
        f"Body System:  {claim.body_system or 'Not specified'}",
        f"Claim Type:   {CLAIM_TYPES.get(claim.claim_type, claim.claim_type)}",
        f"Status:       {claim.status.title()}",
        f"Est. Rating:  {claim.priority_rating}%" if claim.priority_rating else "Est. Rating:  Not set",
        "",
        "CALUZA TRIANGLE STATUS",
        "-" * 40,
        f"[{'✓' if claim.has_diagnosis else '✗'}] Leg 1: Current Diagnosis",
    ]
    if claim.has_diagnosis:
        lines.append(f"    Source: {claim.diagnosis_source or 'Not specified'}")
        lines.append(f"    Date:   {claim.diagnosis_date or 'Not specified'}")

    lines.append(f"[{'✓' if claim.has_inservice_event else '✗'}] Leg 2: In-Service Event")
    if claim.has_inservice_event:
        lines.append(f"    Source: {claim.inservice_source or 'Not specified'}")
        lines.append(f"    Date:   {claim.inservice_date or 'Not specified'}")
        if claim.inservice_description:
            lines.append(f"    Event:  {claim.inservice_description[:200]}")

    lines.append(f"[{'✓' if claim.has_nexus else '✗'}] Leg 3: Medical Nexus")
    if claim.has_nexus:
        lines.append(f"    Source: {claim.nexus_source or 'Not specified'}")
        lines.append(f"    Type:   {claim.nexus_type}")
        verified = "Yes" if claim.nexus_language_verified else "No — VERIFY BEFORE SUBMISSION"
        lines.append(f"    'At least as likely as not' language verified: {verified}")

    lines += [
        "",
        "DENIAL RISK FLAGS",
        "-" * 40,
    ]
    risks = [
        (claim.risk_missing_nexus, "Missing nexus letter — HIGH PRIORITY"),
        (claim.risk_no_continuity, "No in-service event documented (continuity gap risk)"),
        (claim.risk_wrong_form, "Form requirements may not be fully met"),
        (claim.risk_negative_cp_likely, "Nexus language not verified (unfavorable C&P risk)"),
    ]
    for flag, text in risks:
        lines.append(f"  [{'!!' if flag else 'OK'}] {text}")

    if claim.notes:
        lines += ["", "NOTES", "-" * 40, claim.notes]

    lines += ["", "=" * 60]
    path.write_text("\n".join(lines), encoding="utf-8")


def _write_forms_checklist(path: Path, veteran, claims):
    from app.config import VA_FORMS
    lines = [
        "VA FORMS CHECKLIST",
        "=" * 60,
        "",
        "PRIMARY FORMS (required for all claims):",
        f"  [ ] VA Form 21-526EZ  — Application for Disability Compensation",
        f"      (Submit online at VA.gov or mail to regional office)",
        "",
        "PER-CLAIM FORMS:",
    ]

    for claim in claims:
        lines.append(f"\n  Claim: {claim.condition_name} (DC {claim.vasrd_code or 'N/A'})")
        lines.append(f"  [ ] Disability Benefits Questionnaire (DBQ) for this condition")

        if claim.claim_type == "presumptive":
            lines.append(f"  [X] No separate nexus required (presumptive — {claim.presumptive_basis})")

        if claim.inservice_description:
            lines.append(f"  [ ] VA Form 21-4138 (Statement in Support) documenting in-service event")

    # TDIU check
    total_est = sum(c.priority_rating for c in claims if c.priority_rating)
    if any(c.priority_rating and c.priority_rating >= 60 for c in claims):
        lines += [
            "",
            "TDIU FORMS (if applying for Total Disability/Individual Unemployability):",
            "  [ ] VA Form 21-8940 — Veteran's Application for TDIU",
            "  [ ] VA Form 21-4192 — Request for Employment Information",
        ]

    lines += [
        "",
        "BUDDY STATEMENT FORMS:",
        "  [ ] VA Form 21-10210 — Lay/Witness Statement (for each buddy statement)",
        "",
        "APPEAL FORMS (if needed later):",
        "  [ ] VA Form 20-0996 — Decision Review Request: Higher-Level Review",
        "  [ ] VA Form 10182  — Decision Review Request: Board of Veterans Appeals",
        "  [ ] VA Form 20-0995 — Decision Review Request: Supplemental Claim",
        "",
        "WHERE TO FILE:",
        "  Online:  https://www.va.gov/decision-reviews/",
        "  Mail:    VA Claims Intake Center",
        "           PO Box 4444, Janesville, WI 53547-4444",
        f"  Local:   Baltimore VA Regional Office",
        "           31 Hopkins Plaza, Baltimore, MD 21201",
        "",
        "FULLY DEVELOPED CLAIM (FDC) OPTION:",
        "  If ALL evidence is gathered, consider FDC for faster processing.",
        "  NOTE: Adding evidence after FDC submission converts it to Standard Claim.",
    ]

    path.write_text("\n".join(lines), encoding="utf-8")


def _copy_doc(doc, dest_dir: Path):
    from app.core.path_guard import safe_file_path
    src = safe_file_path(Path(doc.filepath))
    if src is None:
        log.warning("Skipping unsafe or missing filepath: %s", doc.filepath)
        return
    try:
        shutil.copy2(str(src), str(dest_dir / src.name))
    except Exception as exc:
        log.warning("Could not copy %s: %s", src, exc)


def _role_to_folder(role: str) -> str:
    mapping = {
        "diagnosis": "Diagnosis_Evidence",
        "inservice_event": "InService_Evidence",
        "nexus": "Nexus_Letter",
        "buddy_statement": "Buddy_Statements",
        "supporting": "Supporting_Evidence",
    }
    return mapping.get(role, "Supporting_Evidence")
