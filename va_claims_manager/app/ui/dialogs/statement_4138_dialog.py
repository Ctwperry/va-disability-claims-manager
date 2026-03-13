"""
VA Form 21-4138 Statement in Support of Claim — Draft Generator.

Generates a pre-filled draft personal statement for the veteran based on
their claim data. The veteran can customize all fields before copying.

Covers both direct and secondary service connection claims, incorporating:
  - Symptom & Treatment Log evidence references
  - Nexus opinion citation (at least as likely as not language)
  - Continuity of symptomatology narrative
  - Functional loss / severity description
"""
from __future__ import annotations
import json
from datetime import date

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QTextEdit, QPushButton, QFrame, QFormLayout, QSpinBox,
    QScrollArea, QWidget, QGroupBox, QApplication,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

import app.db.repositories.claim_repo as claim_repo


class Statement4138Dialog(QDialog):
    """Generate a draft VA Form 21-4138 personal statement for a claim."""

    def __init__(self, claim, veteran, parent=None):
        super().__init__(parent)
        self._claim = claim
        self._veteran = veteran

        # Try to look up primary condition name if this is a secondary claim
        self._primary_condition = ""
        if claim.secondary_to_claim_id:
            primary = claim_repo.get_by_id(claim.secondary_to_claim_id)
            if primary:
                self._primary_condition = primary.condition_name

        self.setWindowTitle(f"Statement in Support of Claim  —  {claim.condition_name}")
        self.setMinimumSize(820, 700)
        self.resize(860, 760)
        self._build_ui()
        self._prefill()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Header
        header = QFrame()
        header.setStyleSheet("background: #1a3a5c; padding: 0;")
        hl = QVBoxLayout(header)
        hl.setContentsMargins(24, 14, 24, 14)
        hl.setSpacing(3)
        title = QLabel("Statement in Support of Claim  (VA Form 21-4138 Draft)")
        title.setStyleSheet("color: white; font-size: 16px; font-weight: bold;")
        hl.addWidget(title)
        sub = QLabel(
            "Fill in the quick-entry fields below, then click Generate to produce "
            "your draft statement. Edit the text directly before copying."
        )
        sub.setStyleSheet("color: #a8c4e0; font-size: 12px;")
        hl.addWidget(sub)
        outer.addWidget(header)

        # Scrollable body
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        body = QWidget()
        layout = QVBoxLayout(body)
        layout.setContentsMargins(24, 16, 24, 16)
        layout.setSpacing(14)

        # ---- Quick-fill inputs ----
        qf_box = QGroupBox("Quick-Fill  (pre-populates the statement template)")
        qf_box.setStyleSheet("QGroupBox { font-weight: bold; font-size: 12px; }")
        qf_layout = QFormLayout(qf_box)
        qf_layout.setSpacing(8)
        qf_layout.setContentsMargins(12, 14, 12, 12)

        # Claim & Veteran (auto-filled, read-only display)
        self._fi_veteran = QLineEdit()
        self._fi_veteran.setReadOnly(True)
        self._fi_veteran.setStyleSheet("background: #f5f5f5; color: #555;")
        qf_layout.addRow("Veteran:", self._fi_veteran)

        self._fi_condition = QLineEdit()
        self._fi_condition.setReadOnly(True)
        self._fi_condition.setStyleSheet("background: #f5f5f5; color: #555;")
        qf_layout.addRow("Condition:", self._fi_condition)

        self._fi_primary = QLineEdit()
        self._fi_primary.setPlaceholderText("(for secondary claims — primary service-connected condition)")
        qf_layout.addRow("Primary Condition:", self._fi_primary)

        qf_layout.addRow(self._divider())

        # Nexus details
        self._fi_doctor = QLineEdit()
        self._fi_doctor.setPlaceholderText("e.g., Dr. Jane Smith, MD")
        qf_layout.addRow("Nexus Doctor Name:", self._fi_doctor)

        self._fi_doc_date = QLineEdit()
        self._fi_doc_date.setPlaceholderText("e.g., 01/20/2024")
        qf_layout.addRow("Date of Nexus Opinion:", self._fi_doc_date)

        self._fi_doc_page = QLineEdit()
        self._fi_doc_page.setPlaceholderText("e.g., Private Records, Page 2")
        qf_layout.addRow("Nexus Document Reference:", self._fi_doc_page)

        self._fi_str_page = QLineEdit()
        self._fi_str_page.setPlaceholderText("e.g., STR PDF, Page 42")
        qf_layout.addRow("STR / In-Service Event Reference:", self._fi_str_page)

        qf_layout.addRow(self._divider())

        # Current symptoms / functional loss
        sym_lbl = QLabel("Current Symptoms & Functional Impact:")
        sym_lbl.setStyleSheet("font-size: 12px; font-weight: bold; color: #1a3a5c;")
        qf_layout.addRow(sym_lbl)

        self._fi_symptoms = QTextEdit()
        self._fi_symptoms.setPlaceholderText(
            "Describe your current symptoms and how they affect daily life and work.\n"
            "Example: Constant lower back pain rated 7/10; cannot sit more than 20 minutes; "
            "requires daily medication; must take breaks every 30 minutes at work."
        )
        self._fi_symptoms.setFixedHeight(80)
        qf_layout.addRow("Symptoms:", self._fi_symptoms)

        # Optional structured fields (functional loss specifics)
        spec_lbl = QLabel("Optional — Specific Functional Limits:")
        spec_lbl.setStyleSheet("font-size: 11px; color: #777;")
        qf_layout.addRow(spec_lbl)

        self._fi_work_impact = QLineEdit()
        self._fi_work_impact.setPlaceholderText(
            "e.g., Must take a break every 30 minutes; interferes with duties as a [Job Title]"
        )
        qf_layout.addRow("Work / Daily Impact:", self._fi_work_impact)

        self._fi_medications = QLineEdit()
        self._fi_medications.setPlaceholderText("e.g., Naproxen 500mg daily, physical therapy 2x/week")
        qf_layout.addRow("Current Treatments:", self._fi_medications)

        layout.addWidget(qf_box)

        # ---- Generate button ----
        gen_row = QHBoxLayout()
        gen_btn = QPushButton("Generate Statement Draft")
        gen_btn.setFixedHeight(34)
        gen_btn.setStyleSheet(
            "QPushButton { background: #1a3a5c; color: white; font-size: 13px; "
            "font-weight: bold; border-radius: 5px; padding: 0 20px; }"
            "QPushButton:hover { background: #0d2a45; }"
        )
        gen_btn.clicked.connect(self._generate)
        gen_row.addWidget(gen_btn)
        gen_row.addStretch()

        note = QLabel(
            "Tip: Include as many evidence references from your Symptom & Treatment Log as possible."
        )
        note.setStyleSheet("font-size: 11px; color: #777; font-style: italic;")
        gen_row.addWidget(note)
        layout.addLayout(gen_row)

        # ---- Statement output ----
        out_lbl = QLabel("Draft Statement  (edit before copying):")
        out_lbl.setStyleSheet("font-size: 12px; font-weight: bold; color: #1a3a5c;")
        layout.addWidget(out_lbl)

        self._output = QTextEdit()
        self._output.setFont(QFont("Times New Roman", 11))
        self._output.setMinimumHeight(320)
        self._output.setStyleSheet(
            "background: white; border: 1px solid #ccc; "
            "padding: 12px; line-height: 1.6;"
        )
        self._output.setPlaceholderText(
            "Click 'Generate Statement Draft' above to populate this section."
        )
        layout.addWidget(self._output)

        scroll.setWidget(body)
        outer.addWidget(scroll, 1)

        # ---- Bottom button bar ----
        btn_bar = QFrame()
        btn_bar.setStyleSheet("background: #f8f9fb; border-top: 1px solid #dde2e8;")
        btn_row = QHBoxLayout(btn_bar)
        btn_row.setContentsMargins(16, 10, 16, 10)
        btn_row.setSpacing(10)

        copy_btn = QPushButton("Copy to Clipboard")
        copy_btn.setFixedHeight(32)
        copy_btn.setStyleSheet(
            "QPushButton { background: #0070c0; color: white; border-radius: 4px; "
            "font-size: 12px; padding: 0 16px; }"
            "QPushButton:hover { background: #005a9e; }"
        )
        copy_btn.clicked.connect(self._copy_to_clipboard)
        btn_row.addWidget(copy_btn)

        btn_row.addStretch()

        close_btn = QPushButton("Close")
        close_btn.setFixedHeight(32)
        close_btn.clicked.connect(self.reject)
        btn_row.addWidget(close_btn)

        outer.addWidget(btn_bar)

    # ------------------------------------------------------------------
    # Pre-fill from claim data
    # ------------------------------------------------------------------

    def _prefill(self):
        vet_name = self._veteran.full_name if self._veteran else ""
        self._fi_veteran.setText(vet_name)
        self._fi_condition.setText(self._claim.condition_name)

        if self._primary_condition:
            self._fi_primary.setText(self._primary_condition)

        # Nexus source often contains doctor name
        if self._claim.nexus_source:
            self._fi_doctor.setText(self._claim.nexus_source)

        # Pre-fill STR/in-service event reference
        if self._claim.inservice_source:
            self._fi_str_page.setText(self._claim.inservice_source)

    # ------------------------------------------------------------------
    # Generation
    # ------------------------------------------------------------------

    def _generate(self):
        c = self._claim
        v = self._veteran

        today = date.today().strftime("%B %d, %Y")
        vet_name = v.full_name if v else "[Veteran Name]"
        vet_branch = v.branch if v else "[Branch]"
        vet_entry = v.entry_date or "[Entry Date]"
        vet_sep = v.separation_date or "[Separation Date]"
        condition = c.condition_name or "[Condition Name]"
        primary = self._fi_primary.text().strip() or (
            "[Primary Service-Connected Condition]"
        )
        doctor = self._fi_doctor.text().strip() or "[Physician Name, Credentials]"
        doc_date = self._fi_doc_date.text().strip() or "[Date of Opinion]"
        doc_page = self._fi_doc_page.text().strip() or "[Private Records, Page X]"
        str_page = self._fi_str_page.text().strip() or "[STR / In-Service Record Reference]"
        symptoms = self._fi_symptoms.toPlainText().strip()
        work_impact = self._fi_work_impact.text().strip()
        medications = self._fi_medications.text().strip()

        # Determine claim type narrative
        is_secondary = c.nexus_type == "secondary" and c.secondary_to_claim_id
        is_presumptive = c.claim_type == "presumptive"

        if is_secondary:
            claim_basis = (
                f"service connection for {condition} as a condition secondary to "
                f"and proximately due to my service-connected {primary}"
            )
            nexus_paragraph = (
                f"My current {condition} is proximately due to and causally aggravated by "
                f"my service-connected {primary}. As documented by {doctor} on {doc_date}, "
                f"my condition is \"at least as likely as not\" caused by or aggravated by "
                f"my service-connected condition (See {doc_page})."
            )
        elif is_presumptive:
            basis_label = c.presumptive_basis or "PACT Act / Presumptive"
            claim_basis = (
                f"service connection for {condition} as a presumptive condition "
                f"under {basis_label}"
            )
            nexus_paragraph = (
                f"My {condition} is recognized as a presumptive condition under {basis_label} "
                f"based on my documented military service. As additionally supported by "
                f"{doctor} on {doc_date}, my condition is \"at least as likely as not\" "
                f"related to my military service (See {doc_page})."
            )
        else:
            event_desc = c.inservice_description or "an in-service injury/event"
            event_date = c.inservice_date or "[In-Service Date]"
            claim_basis = f"direct service connection for {condition}"
            nexus_paragraph = (
                f"My current {condition} is directly related to {event_desc} "
                f"that occurred during my military service on or around {event_date} "
                f"(See {str_page}). As confirmed by {doctor} on {doc_date}, "
                f"my condition is \"at least as likely as not\" caused by my in-service "
                f"injury/event (See {doc_page})."
            )

        # Build symptom log evidence references
        log_entries = []
        try:
            entries = json.loads(c.symptom_log or "[]")
            for e in entries[:6]:  # reference up to 6 entries
                d = e.get("date", "")
                src = e.get("source", "")
                dx = e.get("diagnosis", "")
                if d and src:
                    log_entries.append(f"  • {d} — {src}: {dx}")
        except Exception:
            pass

        evidence_section = ""
        if log_entries:
            evidence_section = (
                "\n\nChronological Evidence:\n" + "\n".join(log_entries)
            )

        # Symptoms section
        if symptoms:
            symptoms_text = symptoms
        else:
            symptoms_text = (
                f"My {condition} significantly affects my daily life and ability to work."
            )

        if work_impact:
            symptoms_text += f"\n\n  Work / Daily Impact: {work_impact}"
        if medications:
            symptoms_text += f"\n\n  Current Treatment: {medications}"

        # Continuity note
        continuity_section = ""
        if c.first_treatment_date:
            continuity_section = (
                f"\n\nContinuity of Symptomatology: My symptoms have been continuous "
                f"since my in-service injury. My first documented post-service treatment "
                f"was on {c.first_treatment_date}."
            )
            if c.continuity_notes:
                continuity_section += f" {c.continuity_notes}"

        # Assemble final statement
        statement = f"""STATEMENT IN SUPPORT OF CLAIM
VA Form 21-4138

To: Department of Veterans Affairs
From: {vet_name}
Date: {today}
Re: Claim for Service Connection — {condition}

──────────────────────────────────────────────

1. CLAIM SUMMARY

I am requesting {claim_basis}. I served in the {vet_branch} from {vet_entry} to {vet_sep}.

──────────────────────────────────────────────

2. THE NEXUS — SERVICE CONNECTION

{nexus_paragraph}

  Chronology: My service treatment records establish the onset and continuity of this condition
  throughout and following my military service (See {str_page}).{evidence_section}

──────────────────────────────────────────────

3. CURRENT SYMPTOMS & FUNCTIONAL LOSS

{symptoms_text}{continuity_section}

──────────────────────────────────────────────

4. CERTIFICATION

I certify that the statements on this form are true and correct to the best of my knowledge
and belief.


_________________________________          Date: ___________________
{vet_name}
"""
        self._output.setPlainText(statement)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _copy_to_clipboard(self):
        text = self._output.toPlainText()
        if text:
            QApplication.clipboard().setText(text)

    @staticmethod
    def _divider() -> QFrame:
        f = QFrame()
        f.setFrameShape(QFrame.Shape.HLine)
        f.setStyleSheet("color: #dde2e8;")
        return f
