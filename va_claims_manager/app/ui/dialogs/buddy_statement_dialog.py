"""
Buddy Statement Template Generator.

Generates a pre-filled VA Form 21-10210 (Lay/Witness Statement) template
based on the current claim's data. The veteran provides this to a buddy,
fellow service member, family member, or anyone who can attest to the
in-service event or current condition.
"""
import html
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTextEdit, QFrame, QApplication, QLineEdit, QFormLayout,
    QGroupBox, QSizePolicy,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont


# ---------------------------------------------------------------------------
# Monthly compensation rates (2025, single veteran, no dependents)
# Included here for the "back pay estimate" note in the template.
# ---------------------------------------------------------------------------

_MONTHLY_RATES_2025 = {
    10: 175.51, 20: 346.95, 30: 537.42, 40: 774.16,
    50: 1102.04, 60: 1395.93, 70: 1759.72, 80: 2044.89,
    90: 2297.96, 100: 3831.30,
}


class BuddyStatementDialog(QDialog):
    """Generate and edit a buddy statement template for a specific claim."""

    def __init__(self, claim, veteran=None, parent=None):
        super().__init__(parent)
        self._claim = claim
        self._veteran = veteran  # Optional Veteran object for pre-filling name
        self.setWindowTitle(f"Buddy Statement Template — {claim.condition_name}")
        self.setMinimumSize(760, 700)
        self.resize(800, 740)
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

        title_lbl = QLabel("Buddy Statement Template Generator")
        title_lbl.setStyleSheet("color: white; font-size: 17px; font-weight: bold;")
        hl.addWidget(title_lbl)

        sub_lbl = QLabel(
            f"VA Form 21-10210 (Lay/Witness Statement)  ·  "
            f"Claim: {html.escape(self._claim.condition_name)}"
        )
        sub_lbl.setStyleSheet("color: #a8c4e0; font-size: 12px;")
        hl.addWidget(sub_lbl)
        layout.addWidget(header)

        # Instructions banner
        instructions = QLabel(
            "  ℹ  Fill in the pre-populated fields below, then share the completed template with your witness. "
            "They sign under penalty of perjury on the actual VA Form 21-10210."
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

        # Witness name
        wit_grp = QVBoxLayout()
        wit_grp.addWidget(QLabel("Witness Full Name:"))
        self._witness_name = QLineEdit()
        self._witness_name.setPlaceholderText("e.g. John A. Smith")
        self._witness_name.setFixedWidth(200)
        self._witness_name.textChanged.connect(self._regenerate)
        wit_grp.addWidget(self._witness_name)
        inputs_layout.addLayout(wit_grp)

        # Relationship
        rel_grp = QVBoxLayout()
        rel_grp.addWidget(QLabel("Relationship to Veteran:"))
        self._relationship = QLineEdit()
        self._relationship.setPlaceholderText("e.g. fellow soldier, spouse, friend")
        self._relationship.setFixedWidth(220)
        self._relationship.textChanged.connect(self._regenerate)
        rel_grp.addWidget(self._relationship)
        inputs_layout.addLayout(rel_grp)

        # Years known
        yrs_grp = QVBoxLayout()
        yrs_grp.addWidget(QLabel("Years Known:"))
        self._years_known = QLineEdit()
        self._years_known.setPlaceholderText("e.g. 12")
        self._years_known.setFixedWidth(70)
        self._years_known.textChanged.connect(self._regenerate)
        yrs_grp.addWidget(self._years_known)
        inputs_layout.addLayout(yrs_grp)

        inputs_layout.addStretch()

        regen_btn = QPushButton("↺  Refresh Template")
        regen_btn.setFixedWidth(150)
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

        note = QLabel("Template is editable — customize before sharing with your witness.")
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

        # Generate initial template
        self._regenerate()

    # ------------------------------------------------------------------
    # Template generation
    # ------------------------------------------------------------------

    def _regenerate(self):
        """Build and display the template based on current inputs."""
        c = self._claim
        veteran_name = (
            self._veteran.full_name if self._veteran else "[VETERAN'S FULL NAME]"
        )
        witness_name = self._witness_name.text().strip() or "[WITNESS FULL NAME]"
        relationship = self._relationship.text().strip() or "[relationship, e.g. fellow soldier]"
        years_known = self._years_known.text().strip() or "___"

        # Build in-service section
        inservice_section = ""
        if c.has_inservice_event and c.inservice_description:
            inservice_section = c.inservice_description.strip()
        elif c.inservice_source:
            inservice_section = f"[Describe the in-service event related to {c.condition_name}]"
        else:
            inservice_section = (
                f"[Describe specifically what you witnessed or have personal knowledge of\n"
                f" regarding the in-service event that caused or contributed to {c.condition_name}]"
            )

        inservice_date = c.inservice_date or "[DATE(S)]"
        inservice_source = c.inservice_source or "[UNIT / LOCATION]"

        # Build nexus note
        nexus_note = ""
        if c.nexus_type == "secondary" and hasattr(c, "secondary_to_claim_id") and c.secondary_to_claim_id:
            nexus_note = (
                f"\nNote: This claim is filed as secondary to {veteran_name}'s "
                f"service-connected condition. The buddy statement should focus on\n"
                f"observable symptoms that demonstrate the current severity of {c.condition_name}."
            )
        elif c.nexus_type == "presumptive":
            nexus_note = (
                f"\nNote: {c.condition_name} may be presumptive under the PACT Act or Agent Orange.\n"
                f"This statement should confirm the veteran's service in the applicable location/era."
            )

        template = f"""\
================================================================================
                    STATEMENT IN SUPPORT OF CLAIM
                         VA Form 21-10210
          Lay/Witness Statement — Under Penalty of Perjury
================================================================================

DATE: _______________________

SECTION A — ABOUT THE WITNESS
--------------------------------------------------------------------------------
I, {witness_name}, make the following statement freely and voluntarily
under penalty of perjury. I understand that a false statement may subject me
to criminal penalties under 18 U.S.C. § 1001 and 38 U.S.C. § 1001.

My relationship to the veteran: {relationship}
I have known {veteran_name} for approximately {years_known} year(s).

We became acquainted through: _______________________________________________

SECTION B — IN-SERVICE EVENT / INCIDENT OBSERVATIONS
--------------------------------------------------------------------------------
Claim relates to: {c.condition_name}{" (VASRD Code " + c.vasrd_code + ")" if c.vasrd_code else ""}

I personally witnessed and/or have direct personal knowledge of the following:

During {veteran_name}'s military service, on or around {inservice_date},
at {inservice_source}:

{inservice_section}

I can confirm the above because: ______________________________________________
______________________________________________________________________________
______________________________________________________________________________

SECTION C — CURRENT CONDITION OBSERVATIONS
--------------------------------------------------------------------------------
Since {veteran_name}'s discharge from military service, I have personally
observed the following regarding their condition of {c.condition_name}:

I have observed that {veteran_name} has difficulty with:
  [ ] Physical activities (describe): ________________________________________
  [ ] Sleep / rest: ___________________________________________________________
  [ ] Work / employment: ______________________________________________________
  [ ] Social activities / relationships: ______________________________________
  [ ] Daily tasks / self-care: ________________________________________________
  [ ] Other: __________________________________________________________________

Specific examples I have personally witnessed:
______________________________________________________________________________
______________________________________________________________________________
______________________________________________________________________________

How often I observe these symptoms / limitations:
  [ ] Daily    [ ] Several times per week    [ ] Weekly    [ ] Less frequently

How the condition has changed over time (better / worse / same):
______________________________________________________________________________
______________________________________________________________________________

SECTION D — CONTINUITY OF SYMPTOMS (if filing years after separation)
--------------------------------------------------------------------------------
I am aware that {veteran_name} has experienced symptoms of {c.condition_name}
continuously since their military service, including:
  ·  [Date/Year I first noticed symptoms]: ____________________________________
  ·  [How I knew the symptoms were related to service]: ______________________
______________________________________________________________________________
{nexus_note}

SECTION E — SIGNATURE (REQUIRED)
--------------------------------------------------------------------------------
I certify that the statements on this form are true and correct to the best of
my knowledge and belief.

Witness Signature: _________________________   Date: _____________

Printed Name: {witness_name}

Address: ___________________________________________________________________

City / State / ZIP: _________________________________________________________

Daytime Phone: _____________________   Email: ________________________________

================================================================================
INSTRUCTIONS FOR SUBMISSION:
1. Complete and sign this statement.
2. Submit with VA Form 21-10210 (available at VA.gov) OR attach this document
   to the veteran's VA Form 21-526EZ claim package.
3. Mail to: VA Claims Intake Center, PO Box 4444, Janesville, WI 53547
   OR upload via VA.gov > My VA > Disability > Evidence Upload
4. Keep a copy for your records.

This template was generated by VA Disability Claims Manager.
It is not a substitute for official VA forms. Consult a VSO for guidance.
================================================================================"""

        self._template_edit.setPlainText(template)

    def _copy(self):
        QApplication.clipboard().setText(self._template_edit.toPlainText())
