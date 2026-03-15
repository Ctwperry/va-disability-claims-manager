"""
Nexus Letter Request Template Generator.

Produces a pre-filled physician request letter that a veteran gives to their doctor,
explicitly requesting an Independent Medical Opinion (IMO) using the
"at least as likely as not" nexus language required by the VA.
"""
import html
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTextEdit, QFrame, QApplication, QLineEdit,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont


class NexusLetterDialog(QDialog):
    """Generate and edit a nexus letter request template for a specific claim."""

    def __init__(self, claim, veteran=None, parent=None):
        super().__init__(parent)
        self._claim = claim
        self._veteran = veteran
        self.setWindowTitle(f"Nexus Letter Request — {claim.condition_name}")
        self.setMinimumSize(780, 740)
        self.resize(820, 780)
        self._build_ui()

    # ------------------------------------------------------------------
    # Build UI
    # ------------------------------------------------------------------

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)

        # Header
        header = QFrame()
        header.setStyleSheet("background: #1a3a5c; padding: 0;")
        hl = QVBoxLayout(header)
        hl.setContentsMargins(24, 14, 24, 14)
        hl.setSpacing(3)

        title_lbl = QLabel("Nexus Letter Request Template")
        title_lbl.setStyleSheet("color: white; font-size: 17px; font-weight: bold;")
        hl.addWidget(title_lbl)

        sub_lbl = QLabel(
            f"Independent Medical Opinion (IMO) Request  ·  "
            f"Claim: {html.escape(self._claim.condition_name)}"
        )
        sub_lbl.setStyleSheet("color: #a8c4e0; font-size: 12px;")
        hl.addWidget(sub_lbl)
        layout.addWidget(header)

        # Instructions banner
        instructions = QLabel(
            "  Give this letter to your treating physician, VA doctor, or private specialist. "
            "They must use the exact phrase 'at least as likely as not' for the VA to accept the opinion."
        )
        instructions.setWordWrap(True)
        instructions.setStyleSheet(
            "background: #e3f0ff; color: #003d80; font-size: 12px; "
            "padding: 8px 16px; border-bottom: 1px solid #b3d1f0;"
        )
        layout.addWidget(instructions)

        # Quick-fill inputs
        inputs_frame = QFrame()
        inputs_frame.setObjectName("dialog_input_frame")
        inputs_layout = QHBoxLayout(inputs_frame)
        inputs_layout.setContentsMargins(20, 12, 20, 12)
        inputs_layout.setSpacing(20)

        # Physician name
        phys_grp = QVBoxLayout()
        phys_grp.addWidget(QLabel("Physician Name:"))
        self._physician_name = QLineEdit()
        self._physician_name.setPlaceholderText("e.g. Dr. Jane Smith")
        self._physician_name.setFixedWidth(200)
        self._physician_name.textChanged.connect(self._regenerate)
        phys_grp.addWidget(self._physician_name)
        inputs_layout.addLayout(phys_grp)

        # Credentials
        cred_grp = QVBoxLayout()
        cred_grp.addWidget(QLabel("Credentials:"))
        self._credentials = QLineEdit()
        self._credentials.setPlaceholderText("MD, DO, NP, PA, etc.")
        self._credentials.setFixedWidth(120)
        self._credentials.textChanged.connect(self._regenerate)
        cred_grp.addWidget(self._credentials)
        inputs_layout.addLayout(cred_grp)

        # Clinic / Hospital
        clinic_grp = QVBoxLayout()
        clinic_grp.addWidget(QLabel("Clinic / Hospital:"))
        self._clinic = QLineEdit()
        self._clinic.setPlaceholderText("e.g. Veterans' Orthopedic Clinic")
        self._clinic.setFixedWidth(240)
        self._clinic.textChanged.connect(self._regenerate)
        clinic_grp.addWidget(self._clinic)
        inputs_layout.addLayout(clinic_grp)

        inputs_layout.addStretch()

        regen_btn = QPushButton("↺  Refresh")
        regen_btn.setFixedWidth(110)
        regen_btn.clicked.connect(self._regenerate)
        inputs_layout.addWidget(regen_btn)

        layout.addWidget(inputs_frame)

        # Editable template
        self._template_edit = QTextEdit()
        self._template_edit.setFont(QFont("Consolas", 11))
        self._template_edit.setStyleSheet(
            "QTextEdit { background: white; border: none; padding: 20px; "
            "color: #1a1a2e; line-height: 1.6; }"
        )
        layout.addWidget(self._template_edit, 1)

        # Footer
        footer = QFrame()
        footer.setObjectName("dialog_footer")
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(16, 10, 16, 10)

        note = QLabel("Template is editable — customize before giving to your physician.")
        note.setStyleSheet("font-size: 11px; color: #777;")
        footer_layout.addWidget(note)
        footer_layout.addStretch()

        btn_copy = QPushButton("Copy to Clipboard")
        btn_copy.setFixedWidth(150)
        btn_copy.clicked.connect(self._copy)
        footer_layout.addWidget(btn_copy)

        btn_close = QPushButton("Close")
        btn_close.setFixedWidth(80)
        btn_close.clicked.connect(self.accept)
        footer_layout.addWidget(btn_close)

        layout.addWidget(footer)

        self._regenerate()

    # ------------------------------------------------------------------
    # Template generation
    # ------------------------------------------------------------------

    def _regenerate(self):
        c = self._claim
        veteran_name = self._veteran.full_name if self._veteran else "[VETERAN'S FULL NAME]"
        dob = self._veteran.dob if self._veteran else "[DATE OF BIRTH]"
        branch = self._veteran.branch if self._veteran else "[BRANCH OF SERVICE]"
        entry = self._veteran.entry_date if self._veteran else "[ENTRY DATE]"
        sep = self._veteran.separation_date if self._veteran else "[SEPARATION DATE]"

        physician = self._physician_name.text().strip() or "[PHYSICIAN'S FULL NAME]"
        credentials = self._credentials.text().strip() or "[CREDENTIALS, e.g. MD]"
        clinic = self._clinic.text().strip() or "[CLINIC / HOSPITAL NAME]"

        inservice_section = c.inservice_description.strip() if c.inservice_description else (
            "[Describe the in-service event, injury, or exposure that caused or contributed "
            f"to {c.condition_name}]"
        )
        inservice_date = c.inservice_date or "[DATE(S) OF EVENT]"
        inservice_source = c.inservice_source or "[UNIT / LOCATION / FACILITY]"

        vasrd_note = f"VASRD Diagnostic Code {c.vasrd_code}" if c.vasrd_code else "applicable VA diagnostic code"

        nexus_type_note = ""
        if c.nexus_type == "secondary" and hasattr(c, "secondary_to_claim_id") and c.secondary_to_claim_id:
            nexus_type_note = (
                f"\nNote: This nexus opinion is for a SECONDARY condition. "
                f"Please opine whether {c.condition_name} was caused or aggravated "
                f"by {veteran_name}'s existing service-connected condition."
            )
        elif c.nexus_type == "presumptive":
            nexus_type_note = (
                f"\nNote: This condition may qualify as a PRESUMPTIVE under the PACT Act "
                f"or Agent Orange regulations. Please confirm the diagnosis and note that "
                f"no direct nexus opinion may be required, though your confirmation is appreciated."
            )

        template = f"""\
================================================================================
                   REQUEST FOR INDEPENDENT MEDICAL OPINION
                    (Nexus Letter for VA Disability Claim)
================================================================================

DATE: _______________________

TO:   {physician}, {credentials}
      {clinic}

FROM: {veteran_name}
      [Address]
      [City, State, ZIP]
      [Phone / Email]

RE:   Independent Medical Opinion — {c.condition_name}
      ({vasrd_note})

================================================================================
Dear {physician},

I am a United States military veteran currently filing a disability compensation
claim with the Department of Veterans Affairs (VA) for:

  Condition: {c.condition_name}
  {"VASRD Code: " + c.vasrd_code if c.vasrd_code else ""}

To support this claim, I respectfully request that you provide an
Independent Medical Opinion (IMO) — commonly called a "Nexus Letter" —
addressing whether my current condition is related to my military service.

================================================================================
SECTION A — VETERAN'S SERVICE HISTORY
--------------------------------------------------------------------------------
Branch of Service: {branch}
Dates of Service:  {entry} to {sep}
Discharge Type:    Honorable (DD-214 available upon request)

================================================================================
SECTION B — IN-SERVICE EVENT / EXPOSURE / INJURY
--------------------------------------------------------------------------------
During my military service, I experienced the following event or exposure that
I believe caused or contributed to my current condition:

Date(s):  {inservice_date}
Location / Unit:  {inservice_source}

Description:
{inservice_section}

Supporting documents (STRs, incident reports, buddy statements) can be
provided upon request.

================================================================================
SECTION C — REQUIRED NEXUS OPINION (VA Standard Language)
--------------------------------------------------------------------------------
The VA requires a specific standard of proof for nexus opinions. Please use
one of the following formulations that most accurately reflects your opinion:

  FAVORABLE (required for service connection):
  ┌─────────────────────────────────────────────────────────────────────────┐
  │  "It is at least as likely as not (50 percent or greater probability)  │
  │  that the veteran's [condition] is related to their active duty        │
  │  military service."                                                    │
  └─────────────────────────────────────────────────────────────────────────┘

  ALTERNATIVE PHRASINGS ALSO ACCEPTED:
  • "More likely than not" (>50%)
  • "As likely as not" (50/50)
  • "Due to" or "caused by" military service

  UNFAVORABLE (use only if your opinion does not support the claim):
  • "Less likely than not" (<50%)
  • "Unlikely to be related to" service
{nexus_type_note}

================================================================================
SECTION D — WHAT TO INCLUDE IN YOUR OPINION
--------------------------------------------------------------------------------
Please include the following in your written IMO:

  1. A statement using the phrase "at least as likely as not" (or equivalent)
  2. Your clinical rationale — why you believe the condition IS or IS NOT
     related to the described in-service event
  3. Reference to relevant medical literature or clinical guidelines,
     if available (optional but strengthens the opinion)
  4. Current diagnosis of {c.condition_name} (if you are the treating provider)
  5. Your credentials, license number, and clinic contact information
  6. Your signature and date

================================================================================
SECTION E — SUBMISSION
--------------------------------------------------------------------------------
Please return the completed opinion on your clinic's official letterhead,
signed and dated.

I will submit your letter together with my VA Form 21-526EZ (Disability Claim)
to the VA Regional Office or upload it via VA.gov.

Questions? You may contact me at: ___________________________________________

Thank you for your time and expertise in assisting with this claim.

Sincerely,

_______________________________      Date: ____________________
{veteran_name}

================================================================================
LEGAL NOTE FOR PHYSICIAN:
This request does not ask you to falsify records or make unsupported statements.
You are only asked to provide your honest medical opinion. VA nexus letters are
standard medical-legal documents routinely provided by physicians.
A false statement to the VA is a federal offense (38 U.S.C. § 1001).
================================================================================

This template was generated by VA Disability Claims Manager.
It is not a substitute for legal or medical advice. Consult a VSO for guidance.\
"""

        self._template_edit.setPlainText(template)

    def _copy(self):
        QApplication.clipboard().setText(self._template_edit.toPlainText())
