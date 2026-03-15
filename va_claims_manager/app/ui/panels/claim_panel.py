"""
Claims panel: list of claims (left) + Caluza Triangle editor (right).
"""
import json
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QFrame, QLineEdit, QComboBox,
    QTextEdit, QCheckBox, QScrollArea, QSplitter, QGroupBox,
    QSpinBox, QMessageBox, QSizePolicy,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import QCompleter

from app.config import BODY_SYSTEMS, CLAIM_TYPES, PACT_ACT_PATH
from app.core.claim import Claim
from app.services.conditions_service import load_vasrd_codes
from app.ui.widgets.triangle_widget import TriangleWidget
from app.ui.widgets.symptom_log_widget import SymptomLogWidget
from app.ui.widgets.evidence_panel import EvidencePanel
from app.ui.dialogs.cp_prep_dialog import CPPrepDialog
from app.ui.dialogs.buddy_statement_dialog import BuddyStatementDialog
from app.ui.dialogs.nexus_letter_dialog import NexusLetterDialog
from app.ui.dialogs.statement_4138_dialog import Statement4138Dialog
import app.db.repositories.claim_repo as claim_repo
import app.db.repositories.document_repo as doc_repo
import app.db.repositories.veteran_repo as veteran_repo


class ClaimPanel(QWidget):
    claims_updated = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._veteran_id: int | None = None
        self._veteran = None           # Veteran object for era/date access
        self._current_claim_id: int | None = None
        self._vasrd_codes: list[dict] = load_vasrd_codes()
        self._pact_entries: list[dict] = self._load_pact_entries()
        self._current_pact_basis: str = ""   # filled when PACT match found
        self._build_ui()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # ---- LEFT: Claims list ----
        left = QWidget()
        left.setObjectName("claim_list_sidebar")
        left.setFixedWidth(260)
        lv = QVBoxLayout(left)
        lv.setContentsMargins(12, 20, 12, 12)
        lv.setSpacing(8)

        claims_hdr = QHBoxLayout()
        claims_title = QLabel("Claims")
        claims_title.setObjectName("section_header")
        claims_hdr.addWidget(claims_title)
        claims_hdr.addStretch()

        self._btn_new_claim = QPushButton("+")
        self._btn_new_claim.setFixedSize(28, 28)
        self._btn_new_claim.setToolTip("New Claim")
        self._btn_new_claim.clicked.connect(self._on_new_claim)
        claims_hdr.addWidget(self._btn_new_claim)
        lv.addLayout(claims_hdr)

        self._claims_list = QListWidget()
        self._claims_list.setStyleSheet(
            "QListWidget { border: none; background: transparent; }"
        )
        self._claims_list.currentItemChanged.connect(self._on_claim_selected)
        lv.addWidget(self._claims_list)

        splitter.addWidget(left)

        # ---- RIGHT: Claim editor ----
        right_scroll = QScrollArea()
        right_scroll.setWidgetResizable(True)
        right_scroll.setFrameShape(QFrame.Shape.NoFrame)

        right = QWidget()
        rv = QVBoxLayout(right)
        rv.setContentsMargins(24, 20, 24, 20)
        rv.setSpacing(12)

        # Header row
        hdr_row = QHBoxLayout()
        self._claim_title = QLabel("Select or create a claim")
        self._claim_title.setObjectName("section_header")
        hdr_row.addWidget(self._claim_title)
        hdr_row.addStretch()

        # Triangle widget
        self._triangle = TriangleWidget(size=130)
        hdr_row.addWidget(self._triangle)

        rv.addLayout(hdr_row)

        # Status badge row
        status_row = QHBoxLayout()
        self._status_badge = QLabel("")
        self._status_badge.setStyleSheet(
            "font-size: 12px; font-weight: bold; padding: 3px 10px; "
            "border-radius: 10px; background: #f0f2f5;"
        )
        status_row.addWidget(self._status_badge)
        status_row.addStretch()

        self._btn_nexus_letter = QPushButton("Nexus Letter")
        self._btn_nexus_letter.setFixedWidth(110)
        self._btn_nexus_letter.setToolTip("Generate a physician request letter for a nexus opinion (IMO)")
        self._btn_nexus_letter.setVisible(False)
        self._btn_nexus_letter.clicked.connect(self._on_nexus_letter)
        status_row.addWidget(self._btn_nexus_letter)

        self._btn_statement = QPushButton("Statement (21-4138)")
        self._btn_statement.setFixedWidth(150)
        self._btn_statement.setToolTip("Generate a draft VA Form 21-4138 personal statement for this claim")
        self._btn_statement.setVisible(False)
        self._btn_statement.clicked.connect(self._on_statement_4138)
        status_row.addWidget(self._btn_statement)

        self._btn_buddy = QPushButton("Buddy Statement")
        self._btn_buddy.setFixedWidth(135)
        self._btn_buddy.setToolTip("Generate a pre-filled VA Form 21-10210 buddy statement template")
        self._btn_buddy.setVisible(False)
        self._btn_buddy.clicked.connect(self._on_buddy_statement)
        status_row.addWidget(self._btn_buddy)

        self._btn_cp_prep = QPushButton("C&P Exam Prep")
        self._btn_cp_prep.setFixedWidth(130)
        self._btn_cp_prep.setToolTip("Generate a C&P exam preparation sheet for this claim")
        self._btn_cp_prep.setVisible(False)
        self._btn_cp_prep.clicked.connect(self._on_cp_prep)
        status_row.addWidget(self._btn_cp_prep)

        self._btn_delete_claim = QPushButton("Delete Claim")
        self._btn_delete_claim.setObjectName("danger_btn")
        self._btn_delete_claim.setFixedWidth(110)
        self._btn_delete_claim.setVisible(False)
        self._btn_delete_claim.clicked.connect(self._on_delete_claim)
        status_row.addWidget(self._btn_delete_claim)

        rv.addLayout(status_row)

        # ---- Basic Info ----
        rv.addWidget(self._section_label("Condition Details"))
        info_card = self._card()
        info_form = QVBoxLayout(info_card)
        info_form.setContentsMargins(16, 16, 16, 16)
        info_form.setSpacing(8)

        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Condition Name *"))
        self._condition_name = QComboBox()
        self._condition_name.setEditable(True)
        self._condition_name.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self._condition_name.lineEdit().setPlaceholderText(
            "Type to search conditions, or enter custom name..."
        )
        self._condition_name.setMinimumWidth(320)
        self._populate_condition_dropdown()
        row1.addWidget(self._condition_name)
        info_form.addLayout(row1)

        row2 = QHBoxLayout()
        row2.addWidget(QLabel("VASRD Code"))
        self._vasrd_code = QLineEdit()
        self._vasrd_code.setPlaceholderText("e.g. 5242")
        self._vasrd_code.setFixedWidth(90)
        self._vasrd_code.textChanged.connect(self._on_vasrd_hint)
        row2.addWidget(self._vasrd_code)
        self._vasrd_hint = QLabel("")
        self._vasrd_hint.setStyleSheet("color: #0070c0; font-size: 11px;")
        row2.addWidget(self._vasrd_hint)
        row2.addStretch()
        info_form.addLayout(row2)

        row3 = QHBoxLayout()
        row3.addWidget(QLabel("Body System"))
        self._body_system = QComboBox()
        self._body_system.addItem("-- Select --", "")
        for s in BODY_SYSTEMS:
            self._body_system.addItem(s, s)
        self._body_system.setFixedWidth(200)
        row3.addWidget(self._body_system)
        row3.addStretch()
        info_form.addLayout(row3)

        row4 = QHBoxLayout()
        row4.addWidget(QLabel("Claim Type"))
        self._claim_type = QComboBox()
        for key, label in CLAIM_TYPES.items():
            self._claim_type.addItem(label, key)
        self._claim_type.setFixedWidth(260)
        self._claim_type.currentIndexChanged.connect(self._on_claim_type_changed)
        row4.addWidget(self._claim_type)
        row4.addStretch()
        info_form.addLayout(row4)

        self._presumptive_row = QHBoxLayout()
        self._presumptive_row.addWidget(QLabel("Presumptive Basis"))
        self._presumptive_basis = QLineEdit()
        self._presumptive_basis.setPlaceholderText("e.g. PACT Act – Burn Pit, Agent Orange")
        self._presumptive_row.addWidget(self._presumptive_basis)
        self._presumptive_widget = QWidget()
        self._presumptive_widget.setLayout(self._presumptive_row)
        self._presumptive_widget.setVisible(False)
        info_form.addWidget(self._presumptive_widget)

        # PACT Act presumptive suggestion banner (shown when condition qualifies)
        self._pact_banner = QFrame()
        self._pact_banner.setStyleSheet(
            "QFrame { background: #fff8e1; border: 1px solid #ffc107; border-radius: 6px; }"
        )
        pact_bl = QHBoxLayout(self._pact_banner)
        pact_bl.setContentsMargins(10, 7, 10, 7)
        pact_bl.setSpacing(8)
        pact_icon = QLabel("⚡")
        pact_icon.setStyleSheet("font-size: 18px; color: #b8610a; background: transparent;")
        pact_bl.addWidget(pact_icon)
        self._pact_banner_text = QLabel("")
        self._pact_banner_text.setWordWrap(True)
        self._pact_banner_text.setStyleSheet(
            "color: #5d4037; font-size: 12px; background: transparent;"
        )
        pact_bl.addWidget(self._pact_banner_text, 1)
        self._btn_apply_presumptive = QPushButton("Set as Presumptive")
        self._btn_apply_presumptive.setFixedWidth(145)
        self._btn_apply_presumptive.clicked.connect(self._apply_pact_presumptive)
        pact_bl.addWidget(self._btn_apply_presumptive)
        self._pact_banner.setVisible(False)
        info_form.addWidget(self._pact_banner)

        row5 = QHBoxLayout()
        row5.addWidget(QLabel("Estimated %"))
        self._priority_rating = QSpinBox()
        self._priority_rating.setRange(0, 100)
        self._priority_rating.setSingleStep(10)
        self._priority_rating.setSuffix("%")
        self._priority_rating.setFixedWidth(80)
        row5.addWidget(self._priority_rating)
        row5.addStretch()
        info_form.addLayout(row5)

        # ---- Effective Date ----
        eff_row = QHBoxLayout()
        eff_lbl = QLabel("Effective Date")
        eff_lbl.setToolTip(
            "The date from which back pay is calculated.\n"
            "Can be the ITF filing date, date of first treatment, date of claim, or separation date."
        )
        eff_row.addWidget(eff_lbl)
        self._effective_date = QLineEdit()
        self._effective_date.setPlaceholderText("YYYY-MM-DD")
        self._effective_date.setFixedWidth(130)
        eff_row.addWidget(self._effective_date)

        eff_basis_lbl = QLabel("  Basis:")
        eff_row.addWidget(eff_basis_lbl)
        self._effective_date_basis = QComboBox()
        for basis in [
            "",
            "Date of claim submission",
            "ITF (Intent to File) date",
            "Date of first treatment / STR entry",
            "Date of disability onset",
            "Date of separation from service",
            "Presumptive: within 1 year of separation",
            "PACT Act enactment (Aug 10, 2022)",
            "Other / Custom",
        ]:
            self._effective_date_basis.addItem(basis, basis)
        self._effective_date_basis.setFixedWidth(280)
        eff_row.addWidget(self._effective_date_basis)
        eff_row.addStretch()
        info_form.addLayout(eff_row)

        rv.addWidget(info_card)

        # ---- Caluza Triangle ----
        rv.addWidget(self._section_label("Caluza Triangle  (Service Connection)"))

        # Leg 1: Diagnosis
        self._leg1 = self._triangle_leg(
            "Leg 1: Current Diagnosis",
            "A formal diagnosis of a physical or mental disability from a qualified provider.",
            checked_attr="_diag_checked",
            source_attr="_diag_source",
            date_attr="_diag_date",
        )
        rv.addWidget(self._leg1)

        # Leg 2: In-Service Event
        self._leg2 = self._triangle_leg(
            "Leg 2: In-Service Event / Injury / Disease",
            "Documented evidence of an event during active duty that could have caused the condition.",
            checked_attr="_insvc_checked",
            source_attr="_insvc_source",
            date_attr="_insvc_date",
        )
        self._insvc_desc_label = QLabel("Event description:")
        self._insvc_desc_label.setStyleSheet("margin-top:4px; color:#555e6e;")
        self._insvc_description = QTextEdit()
        self._insvc_description.setPlaceholderText("Describe the in-service event, injury, or exposure...")
        self._insvc_description.setMaximumHeight(80)
        leg2_inner = self._leg2.layout()
        leg2_inner.addWidget(self._insvc_desc_label)
        leg2_inner.addWidget(self._insvc_description)
        rv.addWidget(self._leg2)

        # Leg 3: Nexus
        self._leg3 = self._triangle_leg(
            "Leg 3: Medical Nexus",
            "A medical opinion linking the current diagnosis to the in-service event.",
            checked_attr="_nexus_checked",
            source_attr="_nexus_source",
            date_attr="_nexus_date",
        )
        self._nexus_verified = QCheckBox(
            'Nexus letter contains "at least as likely as not" language (verified)'
        )
        self._nexus_type_combo = QComboBox()
        for key, label in [
            ("direct", "Direct Nexus"),
            ("secondary", "Secondary to Another Service-Connected Condition"),
            ("presumptive", "Presumptive (PACT Act / Agent Orange)"),
            ("lay_continuity", "Continuity of Symptomatology"),
        ]:
            self._nexus_type_combo.addItem(label, key)
        leg3_inner = self._leg3.layout()
        nexus_row = QHBoxLayout()
        nexus_row.addWidget(QLabel("Nexus type:"))
        nexus_row.addWidget(self._nexus_type_combo)
        nexus_row.addStretch()
        leg3_inner.addLayout(nexus_row)

        # Secondary condition picker (shown only when nexus_type == "secondary")
        self._secondary_widget = QWidget()
        secondary_row = QHBoxLayout(self._secondary_widget)
        secondary_row.setContentsMargins(0, 0, 0, 0)
        sec_lbl = QLabel("Secondary to:")
        sec_lbl.setToolTip("Select the primary service-connected condition this claim is secondary to")
        secondary_row.addWidget(sec_lbl)
        self._secondary_combo = QComboBox()
        self._secondary_combo.setFixedWidth(340)
        self._secondary_combo.setToolTip("The service-connected condition that caused or aggravated this one")
        secondary_row.addWidget(self._secondary_combo)
        secondary_row.addStretch()
        self._secondary_widget.setVisible(False)
        leg3_inner.addWidget(self._secondary_widget)

        self._nexus_type_combo.currentIndexChanged.connect(self._on_nexus_type_changed)

        leg3_inner.addWidget(self._nexus_verified)
        rv.addWidget(self._leg3)

        # ---- Denial Risks ----
        rv.addWidget(self._section_label("Denial Risk Assessment"))
        self._risk_card = self._card()
        risk_layout = QVBoxLayout(self._risk_card)
        risk_layout.setContentsMargins(16, 12, 16, 12)

        self._risk_nexus_lbl = self._risk_label("risk_missing_nexus", "Missing nexus letter")
        self._risk_continuity_lbl = self._risk_label("risk_no_continuity", "No in-service event documented (continuity gap risk)")
        self._risk_form_lbl = self._risk_label("risk_wrong_form", "Incorrect forms may be required")
        self._risk_cp_lbl = self._risk_label("risk_negative_cp_likely", "Nexus language not verified (C&P risk)")

        for lbl in [self._risk_nexus_lbl, self._risk_continuity_lbl,
                    self._risk_form_lbl, self._risk_cp_lbl]:
            risk_layout.addWidget(lbl)
        rv.addWidget(self._risk_card)

        # ---- Continuity of Symptomatology ----
        rv.addWidget(self._section_label("Continuity of Symptomatology"))
        cont_card = self._card()
        cont_layout = QVBoxLayout(cont_card)
        cont_layout.setContentsMargins(16, 12, 16, 12)
        cont_layout.setSpacing(8)

        cont_hint = QLabel(
            "Document the gap between separation and first treatment. "
            "A gap > 1 year triggers a continuity risk that buddy statements can help bridge."
        )
        cont_hint.setWordWrap(True)
        cont_hint.setStyleSheet("color: #555e6e; font-size: 11px;")
        cont_layout.addWidget(cont_hint)

        cont_date_row = QHBoxLayout()
        cont_date_row.addWidget(QLabel("First Treatment Date:"))
        self._first_treatment_date = QLineEdit()
        self._first_treatment_date.setPlaceholderText("YYYY-MM-DD")
        self._first_treatment_date.setFixedWidth(140)
        self._first_treatment_date.textChanged.connect(self._update_continuity_gap)
        cont_date_row.addWidget(self._first_treatment_date)
        self._continuity_gap_lbl = QLabel("")
        self._continuity_gap_lbl.setStyleSheet("font-size: 12px; color: #555e6e; margin-left: 8px;")
        cont_date_row.addWidget(self._continuity_gap_lbl)
        cont_date_row.addStretch()
        cont_layout.addLayout(cont_date_row)

        cont_notes_lbl = QLabel("Continuity Notes (how symptoms persisted after separation):")
        cont_notes_lbl.setStyleSheet("color: #555e6e; font-size: 11px;")
        cont_layout.addWidget(cont_notes_lbl)
        self._continuity_notes = QTextEdit()
        self._continuity_notes.setPlaceholderText(
            "e.g. Symptoms began during deployment 2004, persisted untreated until 2008 VA visit. "
            "Buddy statements from unit members available to bridge gap."
        )
        self._continuity_notes.setMaximumHeight(70)
        cont_layout.addWidget(self._continuity_notes)
        rv.addWidget(cont_card)

        # ---- Evidence Documents ----
        rv.addWidget(self._section_label("Identified Evidence Documents"))
        ev_card = self._card()
        ev_layout = QVBoxLayout(ev_card)
        ev_layout.setContentsMargins(0, 0, 0, 0)
        ev_layout.setSpacing(0)
        self._evidence_panel = EvidencePanel()
        ev_layout.addWidget(self._evidence_panel)
        rv.addWidget(ev_card)

        # ---- Symptom & Treatment Log ----
        rv.addWidget(self._section_label("Symptom & Treatment Log  (\"Evidence Map\")"))
        symp_card = self._card()
        symp_layout = QVBoxLayout(symp_card)
        symp_layout.setContentsMargins(12, 10, 12, 10)
        symp_layout.setSpacing(6)
        self._symptom_log_widget = SymptomLogWidget()
        symp_layout.addWidget(self._symptom_log_widget)
        rv.addWidget(symp_card)

        # ---- Notes ----
        rv.addWidget(self._section_label("Claim Notes"))
        notes_card = self._card()
        notes_layout = QVBoxLayout(notes_card)
        notes_layout.setContentsMargins(16, 12, 16, 12)
        self._notes = QTextEdit()
        self._notes.setPlaceholderText("Strategy notes, VSO contacts, next steps, appeal details...")
        self._notes.setMaximumHeight(100)
        notes_layout.addWidget(self._notes)
        rv.addWidget(notes_card)

        # Save button
        save_row = QHBoxLayout()
        save_row.addStretch()
        self._btn_save = QPushButton("Save Claim")
        self._btn_save.setFixedWidth(130)
        self._btn_save.clicked.connect(self._on_save)
        self._btn_save.setEnabled(False)
        save_row.addWidget(self._btn_save)
        rv.addLayout(save_row)

        rv.addStretch()
        right_scroll.setWidget(right)
        splitter.addWidget(right_scroll)
        splitter.setSizes([260, 900])

        layout.addWidget(splitter)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load_veteran(self, veteran_id: int | None):
        self._veteran_id = veteran_id
        self._veteran = veteran_repo.get_by_id(veteran_id) if veteran_id else None
        self._current_claim_id = None
        self._refresh_list()
        self._refresh_secondary_options()
        self._clear_editor()

    def prefill_new_claim(self, condition: dict):
        """
        Pre-fill the claim editor for a new claim from a condition dict
        (as emitted by ConditionsBrowserPanel.add_claim_requested).
        """
        if not self._veteran_id:
            return
        self._claims_list.clearSelection()
        self._clear_editor()
        self._claim_title.setText("New Claim")
        self._btn_save.setEnabled(True)

        name = condition.get("name", "")
        code = condition.get("code", "")
        system = condition.get("system", "")
        is_presumptive = condition.get("is_presumptive", False)
        basis = condition.get("presumptive_basis", "")

        # Try to match known condition in dropdown; else set free text
        self._condition_name.blockSignals(True)
        matched = False
        for i in range(self._condition_name.count()):
            entry = self._condition_name.itemData(i)
            if entry and entry.get("name") == name:
                self._condition_name.setCurrentIndex(i)
                matched = True
                break
        if not matched:
            self._condition_name.setCurrentText(name)
        self._condition_name.blockSignals(False)

        if code:
            self._vasrd_code.setText(code)
            self._vasrd_hint.setText(name)
        if system:
            self._set_combo(self._body_system, system)

        if is_presumptive:
            idx = self._claim_type.findData("presumptive")
            if idx >= 0:
                self._claim_type.setCurrentIndex(idx)
            self._presumptive_basis.setText(basis)
            self._presumptive_widget.setVisible(True)

        self._condition_name.setFocus()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _triangle_leg(self, title: str, tooltip: str,
                      checked_attr: str, source_attr: str, date_attr: str) -> QGroupBox:
        box = QGroupBox(title)
        layout = QVBoxLayout(box)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(6)

        hint = QLabel(tooltip)
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #555e6e; font-size: 11px;")
        layout.addWidget(hint)

        check = QCheckBox("Documented / Confirmed")
        check.setObjectName(f"leg_check_{checked_attr}")
        check.stateChanged.connect(self._on_leg_changed)
        layout.addWidget(check)
        setattr(self, checked_attr, check)

        src_row = QHBoxLayout()
        src_row.addWidget(QLabel("Source document:"))
        src = QLineEdit()
        src.setPlaceholderText("Filename or description of supporting document")
        src_row.addWidget(src)
        layout.addLayout(src_row)
        setattr(self, source_attr, src)

        date_row = QHBoxLayout()
        date_row.addWidget(QLabel("Date:"))
        dt = QLineEdit()
        dt.setPlaceholderText("YYYY-MM-DD")
        dt.setFixedWidth(130)
        date_row.addWidget(dt)
        date_row.addStretch()
        layout.addLayout(date_row)
        setattr(self, date_attr, dt)

        return box

    def _on_leg_changed(self):
        self._update_triangle_preview()

    def _update_triangle_preview(self):
        self._triangle.set_state(
            diagnosis=self._diag_checked.isChecked(),
            inservice=self._insvc_checked.isChecked(),
            nexus=self._nexus_checked.isChecked(),
        )

    def _section_label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setObjectName("subsection_header")
        return lbl

    @staticmethod
    def _card() -> QFrame:
        card = QFrame()
        card.setObjectName("card")
        return card

    @staticmethod
    def _risk_label(risk_id: str, text: str) -> QLabel:
        lbl = QLabel(f"  ○  {text}")
        lbl.setObjectName(risk_id)
        lbl.setStyleSheet("color: #555e6e; font-size: 12px; padding: 2px 0;")
        return lbl

    def _update_risk_labels(self, claim: Claim):
        def _style(flag):
            if flag:
                return "color: #c0392b; font-size: 12px; font-weight: bold; padding: 2px 0;"
            return "color: #1a7a4a; font-size: 12px; padding: 2px 0;"

        def _mark(flag):
            return "  ✗  " if flag else "  ✓  "

        items = [
            (self._risk_nexus_lbl, claim.risk_missing_nexus, "Nexus letter missing"),
            (self._risk_continuity_lbl, claim.risk_no_continuity, "In-service event not documented (continuity gap risk)"),
            (self._risk_form_lbl, claim.risk_wrong_form, "Form requirements may not be met"),
            (self._risk_cp_lbl, claim.risk_negative_cp_likely, "Nexus language not verified (C&P exam risk)"),
        ]
        for lbl, flag, text in items:
            lbl.setText(f"{_mark(flag)}{text}")
            lbl.setStyleSheet(_style(flag))

    def _on_vasrd_hint(self, code: str):
        hint = ""
        for entry in self._vasrd_codes:
            if entry["code"] == code.strip():
                hint = entry["name"]
                break
        self._vasrd_hint.setText(hint)

    def _on_claim_type_changed(self):
        is_presumptive = self._claim_type.currentData() == "presumptive"
        self._presumptive_widget.setVisible(is_presumptive)

    def _on_nexus_type_changed(self):
        is_secondary = self._nexus_type_combo.currentData() == "secondary"
        self._secondary_widget.setVisible(is_secondary)

    # ------------------------------------------------------------------
    # PACT Act Presumptive Detection
    # ------------------------------------------------------------------

    @staticmethod
    def _load_pact_entries() -> list[dict]:
        """Load pact_act_conditions.json and return list of {era_keywords, condition_keywords, label, basis}."""
        try:
            with open(PACT_ACT_PATH) as f:
                data = json.load(f)
        except Exception:
            return []

        entries = []
        for _key, category in data.items():
            conditions_lower = [c.lower() for c in category.get("conditions", [])]
            # Add short-form keywords (first word of each condition)
            extra = []
            for c in conditions_lower:
                parts = c.split()
                if len(parts) >= 2:
                    extra.append(parts[0])
            entries.append({
                "era_keywords": [e.lower() for e in category.get("exposure_eras", [])],
                "condition_keywords": conditions_lower + extra,
                "label": category.get("label", "Presumptive Condition"),
                "basis": category.get("label", "Presumptive"),
            })
        return entries

    def _check_pact_suggestion(self, condition_text: str):
        """Show PACT presumptive banner if the condition and veteran era match."""
        if not condition_text or not self._veteran:
            self._pact_banner.setVisible(False)
            return

        era_lower = (self._veteran.era or "").lower()
        cond_lower = condition_text.lower()

        matched_label = ""
        matched_basis = ""
        for entry in self._pact_entries:
            # Check era first
            era_match = any(ek in era_lower for ek in entry["era_keywords"])
            if not era_match:
                continue
            # Check condition name
            cond_match = any(
                ck in cond_lower or cond_lower in ck
                for ck in entry["condition_keywords"]
            )
            if cond_match:
                matched_label = entry["label"]
                matched_basis = entry["basis"]
                break

        if matched_label:
            self._current_pact_basis = matched_basis
            self._pact_banner_text.setText(
                f"<b>Presumptive match:</b> {matched_label}  — "
                f"This condition may qualify without a nexus letter. "
                f"Click 'Set as Presumptive' to update the claim type."
            )
            self._pact_banner.setVisible(True)
        else:
            self._current_pact_basis = ""
            self._pact_banner.setVisible(False)

    def _apply_pact_presumptive(self):
        """Switch claim type to presumptive and fill in the PACT basis."""
        idx = self._claim_type.findData("presumptive")
        if idx >= 0:
            self._claim_type.setCurrentIndex(idx)
        if self._current_pact_basis:
            self._presumptive_basis.setText(self._current_pact_basis)
        self._presumptive_widget.setVisible(True)
        self._pact_banner.setVisible(False)

    # ------------------------------------------------------------------
    # Continuity gap calculation
    # ------------------------------------------------------------------

    def _update_continuity_gap(self):
        """Recompute and display the separation-to-first-treatment gap."""
        from datetime import date
        ft_text = self._first_treatment_date.text().strip()
        sep_text = (self._veteran.separation_date or "") if self._veteran else ""

        if not ft_text or not sep_text:
            self._continuity_gap_lbl.setText("")
            return

        try:
            sep_date = date.fromisoformat(sep_text[:10])
            ft_date = date.fromisoformat(ft_text[:10])
        except ValueError:
            self._continuity_gap_lbl.setText("")
            return

        gap_days = (ft_date - sep_date).days
        if gap_days < 0:
            self._continuity_gap_lbl.setText("(date is before separation)")
            self._continuity_gap_lbl.setStyleSheet("font-size: 12px; color: #777;")
            return

        years = gap_days // 365
        months = (gap_days % 365) // 30
        if years > 0:
            gap_str = f"{years}y {months}m gap"
        else:
            gap_str = f"{months} month(s) gap"

        if gap_days > 365:
            self._continuity_gap_lbl.setText(
                f"  ⚠  {gap_str} — consider buddy statement to bridge continuity gap"
            )
            self._continuity_gap_lbl.setStyleSheet("font-size: 12px; color: #c0392b; font-weight: bold;")
        else:
            self._continuity_gap_lbl.setText(f"  ✓  {gap_str}")
            self._continuity_gap_lbl.setStyleSheet("font-size: 12px; color: #1a7a4a;")

    def _refresh_secondary_options(self, exclude_id: int | None = None):
        """Repopulate the secondary-to dropdown with other claims for this veteran."""
        self._secondary_combo.blockSignals(True)
        self._secondary_combo.clear()
        self._secondary_combo.addItem("-- Select primary condition --", None)
        if self._veteran_id:
            for c in claim_repo.get_all(self._veteran_id):
                if c.id != exclude_id:
                    label = f"{c.condition_name}"
                    if c.vasrd_code:
                        label += f"  (DC {c.vasrd_code})"
                    self._secondary_combo.addItem(label, c.id)
        self._secondary_combo.blockSignals(False)

    def _on_statement_4138(self):
        """Open the VA Form 21-4138 draft generator for the current claim."""
        if self._current_claim_id is None:
            return
        # Save symptom log to claim before opening so dialog sees latest data
        claim = claim_repo.get_by_id(self._current_claim_id)
        if claim:
            claim.symptom_log = self._symptom_log_widget.get_data_json()
            dlg = Statement4138Dialog(claim, veteran=self._veteran, parent=self)
            dlg.exec()

    def _on_nexus_letter(self):
        """Open the nexus letter request template generator for the current claim."""
        if self._current_claim_id is None:
            return
        claim = claim_repo.get_by_id(self._current_claim_id)
        if claim:
            dlg = NexusLetterDialog(claim, veteran=self._veteran, parent=self)
            dlg.exec()

    def _on_buddy_statement(self):
        """Open the buddy statement template generator for the current claim."""
        if self._current_claim_id is None:
            return
        claim = claim_repo.get_by_id(self._current_claim_id)
        if claim:
            veteran = veteran_repo.get_by_id(self._veteran_id) if self._veteran_id else None
            dlg = BuddyStatementDialog(claim, veteran=veteran, parent=self)
            dlg.exec()

    def _on_cp_prep(self):
        """Open the C&P Exam Prep sheet for the currently loaded claim."""
        if self._current_claim_id is None:
            return
        claim = claim_repo.get_by_id(self._current_claim_id)
        if claim:
            dlg = CPPrepDialog(claim, parent=self)
            dlg.exec()

    def _populate_condition_dropdown(self):
        """Populate the condition name combo with all VASRD entries and attach a completer."""
        self._condition_name.clear()
        self._condition_name.addItem("")  # blank first entry

        # Build display strings: "Condition Name (CODE) — System"
        self._vasrd_display_map: dict[str, dict] = {}  # display_text -> entry
        for entry in self._vasrd_codes:
            display = f"{entry['name']}  ({entry['code']})  —  {entry['system']}"
            self._condition_name.addItem(display, userData=entry)
            self._vasrd_display_map[display] = entry

        # Completer with substring (contains) matching
        all_items = [self._condition_name.itemText(i)
                     for i in range(self._condition_name.count())]
        completer = QCompleter(all_items, self._condition_name)
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        completer.setFilterMode(Qt.MatchFlag.MatchContains)
        completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        self._condition_name.setCompleter(completer)

        # When user picks from the dropdown, auto-fill VASRD code + body system
        self._condition_name.currentIndexChanged.connect(self._on_condition_selected)
        # Also check PACT when user types freely
        self._condition_name.lineEdit().textChanged.connect(self._check_pact_suggestion)

    def _on_condition_selected(self, index: int):
        """Auto-fill VASRD code and body system when a known condition is chosen."""
        entry = self._condition_name.itemData(index)
        if not entry:
            return
        # Fill VASRD code (block signal to avoid recursive hint)
        self._vasrd_code.blockSignals(True)
        self._vasrd_code.setText(entry.get("code", ""))
        self._vasrd_code.blockSignals(False)
        self._vasrd_hint.setText(entry.get("name", ""))
        # Fill body system
        self._set_combo(self._body_system, entry.get("system", ""))
        # Check PACT presumptive eligibility
        self._check_pact_suggestion(entry.get("name", ""))

    def _get_condition_name_text(self) -> str:
        """Return the plain condition name (strip code/system suffix if picked from list)."""
        text = self._condition_name.currentText().strip()
        # If it matches a known display string, return just the condition name part
        entry = self._vasrd_display_map.get(text) if hasattr(self, "_vasrd_display_map") else None
        if entry:
            return entry["name"]
        return text

    # ------------------------------------------------------------------
    # List refresh
    # ------------------------------------------------------------------

    def _refresh_list(self):
        self._claims_list.blockSignals(True)
        self._claims_list.clear()
        if not self._veteran_id:
            self._claims_list.blockSignals(False)
            return

        claims = claim_repo.get_all(self._veteran_id)
        for claim in claims:
            legs = f"{'✓' if claim.has_diagnosis else '✗'} {'✓' if claim.has_inservice_event else '✗'} {'✓' if claim.has_nexus else '✗'}"
            text = f"{claim.condition_name}\n{claim.vasrd_code or 'No code'}  |  {legs}"
            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, claim.id)
            # Color by completeness
            if claim.triangle_complete:
                item.setForeground(QColor("#1a7a4a"))
            elif claim.triangle_score >= 2:
                item.setForeground(QColor("#0070c0"))
            else:
                item.setForeground(QColor("#c0392b"))
            self._claims_list.addItem(item)

        self._claims_list.blockSignals(False)

    # ------------------------------------------------------------------
    # Editor load/clear
    # ------------------------------------------------------------------

    def _load_claim(self, claim: Claim):
        self._current_claim_id = claim.id
        self._claim_title.setText(claim.condition_name or "New Claim")
        # Try to match existing claim name to a known condition; fall back to free text
        self._condition_name.blockSignals(True)
        matched = False
        for i in range(self._condition_name.count()):
            entry = self._condition_name.itemData(i)
            if entry and entry.get("name") == claim.condition_name:
                self._condition_name.setCurrentIndex(i)
                matched = True
                break
        if not matched:
            self._condition_name.setCurrentText(claim.condition_name)
        self._condition_name.blockSignals(False)
        self._vasrd_code.setText(claim.vasrd_code)
        self._set_combo(self._body_system, claim.body_system)
        self._set_combo(self._claim_type, claim.claim_type)
        self._presumptive_basis.setText(claim.presumptive_basis)
        self._presumptive_widget.setVisible(claim.claim_type == "presumptive")
        self._priority_rating.setValue(claim.priority_rating or 0)

        self._diag_checked.setChecked(claim.has_diagnosis)
        self._diag_source.setText(claim.diagnosis_source)
        self._diag_date.setText(claim.diagnosis_date)

        self._insvc_checked.setChecked(claim.has_inservice_event)
        self._insvc_source.setText(claim.inservice_source)
        self._insvc_date.setText(claim.inservice_date)
        self._insvc_description.setPlainText(claim.inservice_description)

        self._nexus_checked.setChecked(claim.has_nexus)
        self._nexus_source.setText(claim.nexus_source)
        self._nexus_date.setText("")  # Not stored separately
        self._set_combo(self._nexus_type_combo, claim.nexus_type)
        self._nexus_verified.setChecked(claim.nexus_language_verified)

        self._notes.setPlainText(claim.notes)

        # Effective date
        self._effective_date.setText(claim.effective_date or "")
        self._set_combo(self._effective_date_basis, claim.effective_date_basis or "")

        # Secondary condition
        self._refresh_secondary_options(exclude_id=claim.id)
        self._set_combo(self._nexus_type_combo, claim.nexus_type)  # re-set after refresh
        is_secondary = claim.nexus_type == "secondary"
        self._secondary_widget.setVisible(is_secondary)
        if is_secondary and claim.secondary_to_claim_id:
            idx = self._secondary_combo.findData(claim.secondary_to_claim_id)
            if idx >= 0:
                self._secondary_combo.setCurrentIndex(idx)

        # Continuity of symptomatology
        self._first_treatment_date.setText(claim.first_treatment_date or "")
        self._continuity_notes.setPlainText(claim.continuity_notes or "")
        self._update_continuity_gap()

        # Symptom & Treatment Log
        self._symptom_log_widget.load_data(claim.symptom_log or "[]")

        # Check PACT suggestion for this condition
        self._check_pact_suggestion(claim.condition_name)

        self._update_triangle_preview()
        self._update_risk_labels(claim)
        self._evidence_panel.load_evidence(claim.id)

        badge_text = claim.status.replace("_", " ").title()
        badge_color = {"building": "#dde2e8", "ready": "#e8f8f0",
                       "submitted": "#e3f0ff", "decided": "#fff3e0"}.get(claim.status, "#dde2e8")
        self._status_badge.setText(f"  {badge_text}  ")
        self._status_badge.setStyleSheet(
            f"font-size:12px;font-weight:bold;padding:3px 10px;"
            f"border-radius:10px;background:{badge_color};"
        )
        self._btn_save.setEnabled(True)
        self._btn_delete_claim.setVisible(True)
        self._btn_nexus_letter.setVisible(True)
        self._btn_statement.setVisible(True)
        self._btn_cp_prep.setVisible(True)
        self._btn_buddy.setVisible(True)

    def _clear_editor(self):
        self._current_claim_id = None
        self._claim_title.setText("Select or create a claim")
        self._condition_name.blockSignals(True)
        self._condition_name.setCurrentIndex(0)
        self._condition_name.blockSignals(False)
        for w in [self._vasrd_code, self._presumptive_basis,
                  self._diag_source, self._diag_date, self._insvc_source,
                  self._insvc_date, self._nexus_source, self._nexus_date,
                  self._effective_date]:
            w.clear()
        self._vasrd_hint.clear()
        self._insvc_description.clear()
        self._notes.clear()
        self._evidence_panel.clear()
        for cb in [self._diag_checked, self._insvc_checked, self._nexus_checked,
                   self._nexus_verified]:
            cb.setChecked(False)
        self._priority_rating.setValue(0)
        self._body_system.setCurrentIndex(0)
        self._claim_type.setCurrentIndex(0)
        self._nexus_type_combo.setCurrentIndex(0)
        self._effective_date_basis.setCurrentIndex(0)
        self._secondary_widget.setVisible(False)
        self._secondary_combo.setCurrentIndex(0)
        self._triangle.set_state(False, False, False)
        self._status_badge.setText("")
        self._first_treatment_date.clear()
        self._continuity_notes.clear()
        self._continuity_gap_lbl.setText("")
        self._symptom_log_widget.clear()
        self._pact_banner.setVisible(False)
        self._btn_save.setEnabled(False)
        self._btn_delete_claim.setVisible(False)
        self._btn_nexus_letter.setVisible(False)
        self._btn_statement.setVisible(False)
        self._btn_cp_prep.setVisible(False)
        self._btn_buddy.setVisible(False)

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _on_new_claim(self):
        if not self._veteran_id:
            QMessageBox.information(self, "No Veteran", "Please select a veteran first.")
            return
        self._claims_list.clearSelection()
        self._clear_editor()
        self._claim_title.setText("New Claim")
        self._btn_save.setEnabled(True)
        self._condition_name.setFocus()

    def _on_claim_selected(self, current: QListWidgetItem, _):
        if current is None:
            return
        claim_id = current.data(Qt.ItemDataRole.UserRole)
        claim = claim_repo.get_by_id(claim_id)
        if claim:
            self._load_claim(claim)

    def _on_save(self):
        name = self._get_condition_name_text()
        if not name:
            QMessageBox.warning(self, "Validation", "Condition name is required.")
            return

        secondary_id = (
            self._secondary_combo.currentData()
            if self._nexus_type_combo.currentData() == "secondary"
            else None
        )

        c = Claim(
            id=self._current_claim_id,
            veteran_id=self._veteran_id,
            condition_name=name,
            vasrd_code=self._vasrd_code.text().strip(),
            body_system=self._body_system.currentData() or "",
            claim_type=self._claim_type.currentData() or "direct",
            presumptive_basis=self._presumptive_basis.text().strip(),
            has_diagnosis=self._diag_checked.isChecked(),
            diagnosis_source=self._diag_source.text().strip(),
            diagnosis_date=self._diag_date.text().strip(),
            has_inservice_event=self._insvc_checked.isChecked(),
            inservice_source=self._insvc_source.text().strip(),
            inservice_description=self._insvc_description.toPlainText().strip(),
            inservice_date=self._insvc_date.text().strip(),
            has_nexus=self._nexus_checked.isChecked(),
            nexus_source=self._nexus_source.text().strip(),
            nexus_type=self._nexus_type_combo.currentData() or "direct",
            nexus_language_verified=self._nexus_verified.isChecked(),
            priority_rating=self._priority_rating.value() or None,
            notes=self._notes.toPlainText().strip(),
            effective_date=self._effective_date.text().strip(),
            effective_date_basis=self._effective_date_basis.currentData() or "",
            secondary_to_claim_id=secondary_id,
            first_treatment_date=self._first_treatment_date.text().strip(),
            continuity_notes=self._continuity_notes.toPlainText().strip(),
            symptom_log=self._symptom_log_widget.get_data_json(),
        )
        c.compute_risks()

        if self._current_claim_id is None:
            new_id = claim_repo.create(c)
            self._current_claim_id = new_id
            c.id = new_id
        else:
            claim_repo.update(c)

        self._claim_title.setText(c.condition_name)
        self._update_risk_labels(c)
        self._refresh_list()
        self._refresh_secondary_options(exclude_id=self._current_claim_id)
        self._btn_nexus_letter.setVisible(True)
        self._btn_statement.setVisible(True)
        self._btn_cp_prep.setVisible(True)
        self._btn_buddy.setVisible(True)
        self.claims_updated.emit()

    def _on_delete_claim(self):
        if self._current_claim_id is None:
            return
        reply = QMessageBox.question(
            self, "Delete Claim",
            "Delete this claim and all its links to documents?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            claim_repo.delete(self._current_claim_id)
            self._clear_editor()
            self._refresh_list()
            self.claims_updated.emit()

    @staticmethod
    def _set_combo(combo: QComboBox, value: str):
        idx = combo.findData(value)
        if idx >= 0:
            combo.setCurrentIndex(idx)
        else:
            idx = combo.findText(value)
            if idx >= 0:
                combo.setCurrentIndex(idx)
