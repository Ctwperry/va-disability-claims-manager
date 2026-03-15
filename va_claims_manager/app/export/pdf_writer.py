"""
Professional PDF generation for the VA claims export package.

Produces three document types using reportlab:
  write_cover_sheet_pdf()    — package cover page with veteran summary + claims table
  write_claim_summary_pdf()  — per-claim Caluza Triangle status + denial risk report
  write_forms_checklist_pdf() — required VA forms checklist

Color palette follows the VA blue identity (#003366 / #0070c0).
"""
from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# reportlab color palette
# ---------------------------------------------------------------------------

def _colors():
    """Import and return reportlab color objects (deferred to avoid slow startup)."""
    from reportlab.lib.colors import HexColor, white, black, lightgrey
    return {
        "va_blue":    HexColor("#003366"),
        "va_accent":  HexColor("#0070c0"),
        "va_light":   HexColor("#e3f0ff"),
        "success":    HexColor("#1a7a4a"),
        "success_bg": HexColor("#e8f8f0"),
        "danger":     HexColor("#c0392b"),
        "danger_bg":  HexColor("#fdf0ef"),
        "warning":    HexColor("#b8610a"),
        "warning_bg": HexColor("#fff8e1"),
        "gray_bg":    HexColor("#f5f7fa"),
        "gray_border":HexColor("#dde2e8"),
        "text":       HexColor("#1a1a2e"),
        "muted":      HexColor("#555e6e"),
        "white":      white,
        "black":      black,
        "lightgrey":  lightgrey,
    }


# ---------------------------------------------------------------------------
# Shared styles builder
# ---------------------------------------------------------------------------

def _build_styles():
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
    from reportlab.lib.units import inch
    C = _colors()

    base = getSampleStyleSheet()

    styles = {
        "title": ParagraphStyle(
            "Title",
            parent=base["Normal"],
            fontSize=20,
            fontName="Helvetica-Bold",
            textColor=C["white"],
            alignment=TA_CENTER,
            spaceAfter=0,
        ),
        "subtitle": ParagraphStyle(
            "Subtitle",
            parent=base["Normal"],
            fontSize=10,
            fontName="Helvetica",
            textColor=C["white"],
            alignment=TA_CENTER,
            spaceAfter=0,
        ),
        "section": ParagraphStyle(
            "Section",
            parent=base["Normal"],
            fontSize=12,
            fontName="Helvetica-Bold",
            textColor=C["va_blue"],
            spaceBefore=14,
            spaceAfter=4,
            borderPad=0,
        ),
        "body": ParagraphStyle(
            "Body",
            parent=base["Normal"],
            fontSize=10,
            fontName="Helvetica",
            textColor=C["text"],
            spaceAfter=3,
        ),
        "small": ParagraphStyle(
            "Small",
            parent=base["Normal"],
            fontSize=9,
            fontName="Helvetica",
            textColor=C["muted"],
            spaceAfter=2,
        ),
        "bold_body": ParagraphStyle(
            "BoldBody",
            parent=base["Normal"],
            fontSize=10,
            fontName="Helvetica-Bold",
            textColor=C["text"],
            spaceAfter=3,
        ),
        "check_ok": ParagraphStyle(
            "CheckOk",
            parent=base["Normal"],
            fontSize=10,
            fontName="Helvetica-Bold",
            textColor=C["success"],
            spaceAfter=2,
        ),
        "check_fail": ParagraphStyle(
            "CheckFail",
            parent=base["Normal"],
            fontSize=10,
            fontName="Helvetica-Bold",
            textColor=C["danger"],
            spaceAfter=2,
        ),
        "check_warn": ParagraphStyle(
            "CheckWarn",
            parent=base["Normal"],
            fontSize=10,
            fontName="Helvetica-Bold",
            textColor=C["warning"],
            spaceAfter=2,
        ),
        "footer": ParagraphStyle(
            "Footer",
            parent=base["Normal"],
            fontSize=8,
            fontName="Helvetica",
            textColor=C["muted"],
            alignment=TA_CENTER,
        ),
    }
    return styles


# ---------------------------------------------------------------------------
# Cover Sheet
# ---------------------------------------------------------------------------

def write_cover_sheet_pdf(path: Path, veteran, claims: list, docs: list):
    """
    Generate a professional PDF cover sheet for the claims package.

    Sections:
      - VA blue header banner with veteran name
      - Veteran information table
      - Claims summary table (condition, DC code, triangle status, est. rating)
      - Document inventory table
      - Footer with generation timestamp
    """
    try:
        from reportlab.platypus import (
            SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
            HRFlowable, KeepTogether,
        )
        from reportlab.lib.units import inch
        from reportlab.lib.pagesizes import letter
    except ImportError:
        log.warning("reportlab not installed — cannot generate PDF cover sheet")
        return

    C = _colors()
    S = _build_styles()
    doc = SimpleDocTemplate(
        str(path),
        pagesize=letter,
        leftMargin=0.75 * inch,
        rightMargin=0.75 * inch,
        topMargin=0.6 * inch,
        bottomMargin=0.6 * inch,
    )
    story = []
    W = letter[0] - 1.5 * inch   # usable width

    # ---- Header banner ----
    header_data = [[
        Paragraph("VA DISABILITY CLAIMS PACKAGE", S["title"]),
        Paragraph(f"{veteran.full_name}", S["subtitle"]),
    ]]
    header_table = Table(header_data, colWidths=[W])
    header_table.setStyle(TableStyle([
        ("BACKGROUND",  (0, 0), (-1, -1), C["va_blue"]),
        ("TOPPADDING",  (0, 0), (-1, -1), 14),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 14),
        ("LEFTPADDING",  (0, 0), (-1, -1), 20),
        ("RIGHTPADDING", (0, 0), (-1, -1), 20),
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [C["va_blue"]]),
    ]))
    story.append(header_table)
    story.append(Spacer(1, 14))

    # ---- Veteran information ----
    story.append(Paragraph("VETERAN INFORMATION", S["section"]))
    story.append(HRFlowable(width=W, thickness=1, color=C["va_blue"], spaceAfter=6))

    vet_data = [
        ["Full Name",      veteran.full_name or "—"],
        ["Branch",         veteran.branch or "—"],
        ["Service Era",    veteran.era or "—"],
        ["Service Dates",  f"{veteran.entry_date or '?'}  to  {veteran.separation_date or '?'}"],
        ["Discharge Type", veteran.discharge_type or "—"],
        ["DD-214 on File", "Yes" if veteran.dd214_on_file else "No"],
    ]
    vet_table = _info_table(vet_data, W, C, S)
    story.append(vet_table)
    story.append(Spacer(1, 10))

    # ---- Claims summary ----
    story.append(Paragraph("CLAIMS SUMMARY", S["section"]))
    story.append(HRFlowable(width=W, thickness=1, color=C["va_blue"], spaceAfter=6))

    from app.core.rating_calculator import combined_rating
    ratings = [c.priority_rating for c in claims if c.priority_rating]
    if ratings:
        est_combined = combined_rating(ratings)
        story.append(Paragraph(
            f"Estimated Combined Rating: <b>{est_combined}%</b>  |  "
            f"Total Claims: {len(claims)}  |  "
            f"Triangle Complete: {sum(1 for c in claims if c.triangle_complete)}/{len(claims)}",
            S["body"],
        ))
        story.append(Spacer(1, 6))

    if claims:
        col_w = [W * 0.34, W * 0.12, W * 0.30, W * 0.12, W * 0.12]
        claim_rows = [[
            Paragraph("<b>Condition</b>", S["bold_body"]),
            Paragraph("<b>DC Code</b>", S["bold_body"]),
            Paragraph("<b>Triangle</b>", S["bold_body"]),
            Paragraph("<b>Rating</b>", S["bold_body"]),
            Paragraph("<b>Risks</b>", S["bold_body"]),
        ]]
        for claim in claims:
            dx  = "✓" if claim.has_diagnosis     else "✗"
            svc = "✓" if claim.has_inservice_event else "✗"
            nex = "✓" if claim.has_nexus          else "✗"
            tri = f"Dx:{dx}  Svc:{svc}  Nex:{nex}"
            tri_style = S["check_ok"] if claim.triangle_complete else S["check_fail"]
            claim_rows.append([
                Paragraph(claim.condition_name, S["body"]),
                Paragraph(claim.vasrd_code or "—", S["small"]),
                Paragraph(tri, tri_style),
                Paragraph(f"{claim.priority_rating}%" if claim.priority_rating else "—", S["body"]),
                Paragraph(str(claim.risk_count) if claim.risk_count else "None", S["body"]),
            ])
        ct = Table(claim_rows, colWidths=col_w, repeatRows=1)
        ct.setStyle(_table_style(C))
        story.append(ct)
    else:
        story.append(Paragraph("No claims in this package.", S["small"]))

    story.append(Spacer(1, 10))

    # ---- Document inventory ----
    story.append(Paragraph("DOCUMENT INVENTORY", S["section"]))
    story.append(HRFlowable(width=W, thickness=1, color=C["va_blue"], spaceAfter=6))

    from app.config import DOC_TYPES
    from collections import Counter
    type_counts = Counter(d.doc_type for d in docs)
    total_pages = sum(d.page_count for d in docs)

    story.append(Paragraph(
        f"Total documents: <b>{len(docs)}</b>  |  Total pages: <b>{total_pages:,}</b>",
        S["body"],
    ))
    story.append(Spacer(1, 6))

    if type_counts:
        inv_data = [[
            Paragraph("<b>Document Type</b>", S["bold_body"]),
            Paragraph("<b>Count</b>", S["bold_body"]),
        ]]
        for doc_type, count in sorted(type_counts.items()):
            label = DOC_TYPES.get(doc_type, doc_type)
            inv_data.append([
                Paragraph(label, S["body"]),
                Paragraph(str(count), S["body"]),
            ])
        inv_table = Table(inv_data, colWidths=[W * 0.78, W * 0.22], repeatRows=1)
        inv_table.setStyle(_table_style(C))
        story.append(inv_table)

    # ---- Footer ----
    story.append(Spacer(1, 20))
    story.append(HRFlowable(width=W, thickness=0.5, color=C["gray_border"]))
    story.append(Spacer(1, 6))
    story.append(Paragraph(
        f"Generated: {datetime.now().strftime('%B %d, %Y  %H:%M')}  |  "
        "VA Disability Claims Manager  |  "
        "NOT a substitute for legal or medical advice — consult a VSO or accredited VA attorney",
        S["footer"],
    ))

    try:
        doc.build(story)
    except Exception as exc:
        log.error("Failed to build cover sheet PDF: %s", exc)
        raise


# ---------------------------------------------------------------------------
# Claim Summary
# ---------------------------------------------------------------------------

def write_claim_summary_pdf(path: Path, claim, veteran):
    """
    Generate a per-claim PDF showing Caluza Triangle status, denial risks, and notes.
    """
    try:
        from reportlab.platypus import (
            SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
            HRFlowable,
        )
        from reportlab.lib.units import inch
        from reportlab.lib.pagesizes import letter
    except ImportError:
        log.warning("reportlab not installed — cannot generate PDF claim summary")
        return

    C = _colors()
    S = _build_styles()

    from app.config import CLAIM_TYPES
    doc = SimpleDocTemplate(
        str(path),
        pagesize=letter,
        leftMargin=0.75 * inch,
        rightMargin=0.75 * inch,
        topMargin=0.6 * inch,
        bottomMargin=0.6 * inch,
    )
    story = []
    W = letter[0] - 1.5 * inch

    # ---- Header ----
    header_data = [[
        Paragraph(f"CLAIM SUMMARY", S["title"]),
        Paragraph(claim.condition_name, S["subtitle"]),
    ]]
    header_table = Table(header_data, colWidths=[W])
    header_table.setStyle(TableStyle([
        ("BACKGROUND",  (0, 0), (-1, -1), C["va_blue"]),
        ("TOPPADDING",  (0, 0), (-1, -1), 12),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
        ("LEFTPADDING",  (0, 0), (-1, -1), 20),
        ("RIGHTPADDING", (0, 0), (-1, -1), 20),
    ]))
    story.append(header_table)
    story.append(Spacer(1, 14))

    # ---- Claim metadata ----
    story.append(Paragraph("CLAIM DETAILS", S["section"]))
    story.append(HRFlowable(width=W, thickness=1, color=C["va_blue"], spaceAfter=6))

    meta_data = [
        ["VASRD Code",   claim.vasrd_code or "Not specified"],
        ["Body System",  claim.body_system or "Not specified"],
        ["Claim Type",   CLAIM_TYPES.get(claim.claim_type, claim.claim_type)],
        ["Status",       claim.status.title()],
        ["Est. Rating",  f"{claim.priority_rating}%" if claim.priority_rating else "Not set"],
    ]
    story.append(_info_table(meta_data, W, C, S))
    story.append(Spacer(1, 10))

    # ---- Caluza Triangle ----
    story.append(Paragraph("CALUZA TRIANGLE STATUS", S["section"]))
    story.append(HRFlowable(width=W, thickness=1, color=C["va_blue"], spaceAfter=6))

    def _leg(check, label, source, date, extra=None):
        rows = []
        icon = "✓" if check else "✗"
        style = S["check_ok"] if check else S["check_fail"]
        rows.append([Paragraph(f"{icon}  Leg: {label}", style), ""])
        if check:
            if source:
                rows.append(["", Paragraph(f"Source: {source}", S["small"])])
            if date:
                rows.append(["", Paragraph(f"Date:   {date}", S["small"])])
            if extra:
                rows.append(["", Paragraph(f"Notes:  {extra[:200]}", S["small"])])
        return rows

    tri_rows: list = []
    tri_rows += _leg(
        claim.has_diagnosis, "Current Diagnosis",
        claim.diagnosis_source, claim.diagnosis_date,
    )
    nex_extra = None
    if claim.has_nexus:
        nex_extra = (
            f"Type: {claim.nexus_type}  |  "
            f"'At least as likely' verified: "
            f"{'Yes' if claim.nexus_language_verified else 'NO — VERIFY BEFORE SUBMISSION'}"
        )
    tri_rows += _leg(
        claim.has_inservice_event, "In-Service Event",
        claim.inservice_source, claim.inservice_date,
        claim.inservice_description,
    )
    tri_rows += _leg(
        claim.has_nexus, "Medical Nexus",
        claim.nexus_source, None,
        nex_extra,
    )

    tri_table = Table(tri_rows, colWidths=[W * 0.35, W * 0.65])
    tri_table.setStyle(TableStyle([
        ("VALIGN",      (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING",  (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(tri_table)
    story.append(Spacer(1, 10))

    # ---- Denial risk flags ----
    story.append(Paragraph("DENIAL RISK FLAGS", S["section"]))
    story.append(HRFlowable(width=W, thickness=1, color=C["va_blue"], spaceAfter=6))

    risks = [
        (claim.risk_missing_nexus,      "Missing nexus letter — HIGH PRIORITY"),
        (claim.risk_no_continuity,      "No in-service event documented (continuity gap risk)"),
        (claim.risk_wrong_form,         "Form requirements may not be fully met"),
        (claim.risk_negative_cp_likely, "Nexus language not verified (unfavorable C&P risk)"),
    ]
    risk_rows = []
    for flag, text in risks:
        if flag:
            risk_rows.append([
                Paragraph("!! RISK", S["check_fail"]),
                Paragraph(text, S["check_fail"]),
            ])
        else:
            risk_rows.append([
                Paragraph("OK", S["check_ok"]),
                Paragraph(text, S["body"]),
            ])
    rt = Table(risk_rows, colWidths=[W * 0.15, W * 0.85])
    rt.setStyle(TableStyle([
        ("VALIGN",      (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING",  (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [C["white"], C["gray_bg"]]),
    ]))
    story.append(rt)

    # ---- Notes ----
    if claim.notes:
        story.append(Spacer(1, 10))
        story.append(Paragraph("NOTES", S["section"]))
        story.append(HRFlowable(width=W, thickness=1, color=C["va_blue"], spaceAfter=6))
        # Truncate very long notes for the summary
        notes_text = claim.notes[:2000]
        if len(claim.notes) > 2000:
            notes_text += "\n…(truncated, see full notes in the application)"
        for line in notes_text.split("\n")[:40]:
            story.append(Paragraph(line or " ", S["small"]))

    # ---- Footer ----
    story.append(Spacer(1, 20))
    story.append(HRFlowable(width=W, thickness=0.5, color=C["gray_border"]))
    story.append(Spacer(1, 6))
    story.append(Paragraph(
        f"Generated: {datetime.now().strftime('%B %d, %Y  %H:%M')}  |  "
        "VA Disability Claims Manager",
        S["footer"],
    ))

    try:
        doc.build(story)
    except Exception as exc:
        log.error("Failed to build claim summary PDF for %s: %s", claim.condition_name, exc)
        raise


# ---------------------------------------------------------------------------
# Forms Checklist
# ---------------------------------------------------------------------------

def write_forms_checklist_pdf(path: Path, veteran, claims: list):
    """
    Generate a VA forms checklist PDF tailored to the veteran's specific claims.
    """
    try:
        from reportlab.platypus import (
            SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
            HRFlowable,
        )
        from reportlab.lib.units import inch
        from reportlab.lib.pagesizes import letter
    except ImportError:
        log.warning("reportlab not installed — cannot generate PDF forms checklist")
        return

    C = _colors()
    S = _build_styles()

    doc = SimpleDocTemplate(
        str(path),
        pagesize=letter,
        leftMargin=0.75 * inch,
        rightMargin=0.75 * inch,
        topMargin=0.6 * inch,
        bottomMargin=0.6 * inch,
    )
    story = []
    W = letter[0] - 1.5 * inch

    # Header
    header_data = [[Paragraph("VA FORMS CHECKLIST", S["title"])]]
    ht = Table(header_data, colWidths=[W])
    ht.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), C["va_blue"]),
        ("TOPPADDING",    (0, 0), (-1, -1), 14),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 14),
        ("LEFTPADDING",   (0, 0), (-1, -1), 20),
    ]))
    story.append(ht)
    story.append(Spacer(1, 14))

    def _checkbox_row(checked: bool, label: str, note: str = "") -> list:
        mark = "☑" if checked else "☐"
        cols = [Paragraph(mark, S["bold_body"]), Paragraph(label, S["body"])]
        if note:
            cols.append(Paragraph(note, S["small"]))
        else:
            cols.append(Paragraph("", S["small"]))
        return cols

    # Primary forms
    story.append(Paragraph("PRIMARY FORMS (required for all claims)", S["section"]))
    story.append(HRFlowable(width=W, thickness=1, color=C["va_blue"], spaceAfter=6))

    primary_rows = [
        _checkbox_row(False, "VA Form 21-526EZ", "Application for Disability Compensation"),
    ]
    pt = Table(primary_rows, colWidths=[W * 0.06, W * 0.38, W * 0.56])
    pt.setStyle(_checklist_style(C))
    story.append(pt)
    story.append(Spacer(1, 10))

    # Per-claim forms
    story.append(Paragraph("PER-CLAIM FORMS", S["section"]))
    story.append(HRFlowable(width=W, thickness=1, color=C["va_blue"], spaceAfter=6))

    for claim in claims:
        story.append(Paragraph(
            f"{claim.condition_name}  (DC {claim.vasrd_code or 'N/A'})",
            S["bold_body"],
        ))
        per_rows = [
            _checkbox_row(False, f"DBQ for this condition", "Disability Benefits Questionnaire"),
        ]
        if claim.claim_type == "presumptive":
            per_rows.append(_checkbox_row(
                True, "No nexus required",
                f"Presumptive — {claim.presumptive_basis or 'PACT Act'}",
            ))
        if claim.inservice_description:
            per_rows.append(_checkbox_row(
                False, "VA Form 21-4138",
                "Statement documenting in-service event",
            ))
        ct = Table(per_rows, colWidths=[W * 0.06, W * 0.38, W * 0.56])
        ct.setStyle(_checklist_style(C))
        story.append(ct)
        story.append(Spacer(1, 6))

    # TDIU
    if any(c.priority_rating and c.priority_rating >= 60 for c in claims):
        story.append(Paragraph("TDIU FORMS (Total Disability / Individual Unemployability)", S["section"]))
        story.append(HRFlowable(width=W, thickness=1, color=C["warning"], spaceAfter=6))
        tdiu_rows = [
            _checkbox_row(False, "VA Form 21-8940", "Veteran's Application for TDIU"),
            _checkbox_row(False, "VA Form 21-4192", "Request for Employment Information"),
        ]
        tt = Table(tdiu_rows, colWidths=[W * 0.06, W * 0.38, W * 0.56])
        tt.setStyle(_checklist_style(C))
        story.append(tt)
        story.append(Spacer(1, 10))

    # Buddy + Appeal
    story.append(Paragraph("BUDDY STATEMENT & APPEAL FORMS", S["section"]))
    story.append(HRFlowable(width=W, thickness=1, color=C["va_blue"], spaceAfter=6))
    misc_rows = [
        _checkbox_row(False, "VA Form 21-10210", "Lay/Witness Statement (buddy statement)"),
        _checkbox_row(False, "VA Form 20-0996", "Decision Review: Higher-Level Review"),
        _checkbox_row(False, "VA Form 10182",   "Decision Review: Board of Veterans Appeals"),
        _checkbox_row(False, "VA Form 20-0995", "Decision Review: Supplemental Claim"),
    ]
    mt = Table(misc_rows, colWidths=[W * 0.06, W * 0.38, W * 0.56])
    mt.setStyle(_checklist_style(C))
    story.append(mt)
    story.append(Spacer(1, 10))

    # Filing locations
    story.append(Paragraph("WHERE TO FILE", S["section"]))
    story.append(HRFlowable(width=W, thickness=1, color=C["va_blue"], spaceAfter=6))
    for line in [
        "Online:  https://www.va.gov/decision-reviews/",
        "Mail:    VA Claims Intake Center, PO Box 4444, Janesville, WI 53547-4444",
        "Local:   Find your regional office at va.gov/find-locations",
        "",
        "Fully Developed Claim (FDC) option: If ALL evidence is gathered, submit as FDC for faster processing.",
        "Note: Adding evidence after FDC submission converts it to a Standard Claim.",
    ]:
        story.append(Paragraph(line or " ", S["body"] if line else S["small"]))

    # Footer
    story.append(Spacer(1, 20))
    story.append(HRFlowable(width=W, thickness=0.5, color=C["gray_border"]))
    story.append(Spacer(1, 6))
    story.append(Paragraph(
        f"Generated: {datetime.now().strftime('%B %d, %Y  %H:%M')}  |  "
        "VA Disability Claims Manager  |  "
        "NOT a substitute for legal or medical advice",
        S["footer"],
    ))

    try:
        doc.build(story)
    except Exception as exc:
        log.error("Failed to build forms checklist PDF: %s", exc)
        raise


# ---------------------------------------------------------------------------
# Shared table helpers
# ---------------------------------------------------------------------------

def _info_table(rows: list[list], width: float, C: dict, S: dict):
    """Two-column label / value table for veteran info, claim metadata, etc."""
    from reportlab.platypus import Table, TableStyle, Paragraph
    data = [
        [Paragraph(f"<b>{label}</b>", S["small"]),
         Paragraph(str(value), S["body"])]
        for label, value in rows
    ]
    t = Table(data, colWidths=[width * 0.28, width * 0.72])
    t.setStyle(TableStyle([
        ("VALIGN",      (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING",  (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [C["white"], C["gray_bg"]]),
        ("LINEBELOW",   (0, 0), (-1, -2), 0.25, C["gray_border"]),
    ]))
    return t


def _table_style(C: dict):
    from reportlab.platypus import TableStyle
    return TableStyle([
        ("BACKGROUND",   (0, 0), (-1, 0), C["va_light"]),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [C["white"], C["gray_bg"]]),
        ("GRID",         (0, 0), (-1, -1), 0.25, C["gray_border"]),
        ("VALIGN",       (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING",   (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 5),
        ("LEFTPADDING",  (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ])


def _checklist_style(C: dict):
    from reportlab.platypus import TableStyle
    return TableStyle([
        ("VALIGN",      (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING",  (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [C["white"], C["gray_bg"]]),
        ("LINEBELOW",   (0, 0), (-1, -2), 0.25, C["gray_border"]),
    ])
