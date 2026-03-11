"""
Claims panel: list of claims (left) + Caluza Triangle editor (right).
"""
import json
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QFrame, QLineEdit, QComboBox,
    QTextEdit, QCheckBox, QScrollArea, QSplitter, QGroupBox,
    QSpinBox, QMessageBox, QSizePolicy
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import QCompleter

from app.config import BODY_SYSTEMS, CLAIM_TYPES, VASRD_CODES_PATH
from app.core.claim import Claim
from app.ui.widgets.triangle_widget import TriangleWidget
import app.db.repositories.claim_repo as claim_repo
import app.db.repositories.document_repo as doc_repo


class ClaimPanel(QWidget):
    claims_updated = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._veteran_id: int | None = None
        self._current_claim_id: int | None = None
        self._vasrd_codes: list[dict] = self._load_vasrd()
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
        left.setFixedWidth(260)
        left.setStyleSheet("background-color: #f8f9fb; border-right: 1px solid #dde2e8;")
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

        # ---- Evidence Documents ----
        self._evidence_header = self._section_label("Identified Evidence Documents")
        rv.addWidget(self._evidence_header)
        self._evidence_card = self._card()
        self._evidence_layout = QVBoxLayout(self._evidence_card)
        self._evidence_layout.setContentsMargins(12, 10, 12, 10)
        self._evidence_layout.setSpacing(6)
        self._evidence_empty_lbl = QLabel(
            "  No evidence documents linked yet.\n"
            "  Use 'Analyze Records' in the Documents tab to auto-detect evidence,\n"
            "  or assign documents manually via the role dropdowns above."
        )
        self._evidence_empty_lbl.setStyleSheet("color: #888; font-size: 12px; padding: 6px;")
        self._evidence_layout.addWidget(self._evidence_empty_lbl)
        rv.addWidget(self._evidence_card)

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
        self._current_claim_id = None
        self._refresh_list()
        self._clear_editor()

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

    @staticmethod
    def _load_vasrd() -> list[dict]:
        try:
            import json
            with open(VASRD_CODES_PATH) as f:
                data = json.load(f)
            return data.get("codes", [])
        except Exception:
            return []

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

    def _get_condition_name_text(self) -> str:
        """Return the plain condition name (strip code/system suffix if picked from list)."""
        text = self._condition_name.currentText().strip()
        # If it matches a known display string, return just the condition name part
        entry = self._vasrd_display_map.get(text) if hasattr(self, "_vasrd_display_map") else None
        if entry:
            return entry["name"]
        return text

    # ------------------------------------------------------------------
    # Evidence documents panel
    # ------------------------------------------------------------------

    def _clear_evidence(self):
        """Remove all evidence document cards and show the empty-state label."""
        layout = self._evidence_layout
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget and widget is not self._evidence_empty_lbl:
                widget.deleteLater()
        self._evidence_empty_lbl.setVisible(True)
        layout.addWidget(self._evidence_empty_lbl)

    def _load_evidence(self, claim_id: int):
        """Load claim_documents for this claim and render a card for each linked document."""
        import json as _json
        import html as _html
        from app.db.connection import get_connection

        self._clear_evidence()

        conn = get_connection()
        rows = conn.execute(
            """
            SELECT cd.claim_id, cd.document_id, cd.role, cd.notes,
                   d.filename, d.doc_type
            FROM claim_documents cd
            JOIN documents d ON d.id = cd.document_id
            WHERE cd.claim_id = ?
            ORDER BY d.filename
            """,
            (claim_id,),
        ).fetchall()

        if not rows:
            return

        self._evidence_empty_lbl.setVisible(False)

        for row in rows:
            doc_id = row["document_id"]
            row_role = row["role"] or "supporting"
            filename = row["filename"] or "Unknown file"
            doc_type = row["doc_type"] or "Document"
            role = row_role
            notes_raw = row["notes"] or "{}"

            try:
                notes = _json.loads(notes_raw)
            except Exception:
                notes = {}

            pages = notes.get("pages", [])
            auto_detected = notes.get("auto_detected", False)

            card = QFrame()
            card.setObjectName("card")
            card.setStyleSheet(
                "QFrame#card { border: 1px solid #d0d7de; border-radius: 6px; "
                "background: #f8f9fa; margin-bottom: 2px; }"
            )
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(10, 8, 10, 8)
            card_layout.setSpacing(4)

            # Header row: filename + doc type badge
            header_row = QHBoxLayout()
            fname_lbl = QLabel(f"<b>{_html.escape(filename)}</b>")
            fname_lbl.setStyleSheet("font-size: 13px;")
            header_row.addWidget(fname_lbl)

            type_badge = QLabel(f"  {_html.escape(doc_type)}  ")
            type_badge.setStyleSheet(
                "font-size: 11px; padding: 1px 6px; border-radius: 8px; "
                "background: #dde3ea; color: #444;"
            )
            header_row.addWidget(type_badge)
            if auto_detected:
                auto_badge = QLabel("  Auto-detected  ")
                auto_badge.setStyleSheet(
                    "font-size: 11px; padding: 1px 6px; border-radius: 8px; "
                    "background: #e3f0ff; color: #0050a0;"
                )
                header_row.addWidget(auto_badge)
            header_row.addStretch()
            card_layout.addLayout(header_row)

            # Role selector
            role_row = QHBoxLayout()
            role_lbl = QLabel("Role:")
            role_lbl.setStyleSheet("font-size: 12px; color: #555;")
            role_row.addWidget(role_lbl)

            role_combo = QComboBox()
            role_combo.addItem("Supporting Evidence", "supporting")
            role_combo.addItem("Diagnosis Evidence", "diagnosis")
            role_combo.addItem("In-Service Evidence", "inservice_event")
            role_combo.addItem("Nexus Letter", "nexus")
            role_combo.addItem("Buddy Statement", "buddy_statement")
            # Select current role
            for i in range(role_combo.count()):
                if role_combo.itemData(i) == role:
                    role_combo.setCurrentIndex(i)
                    break
            role_combo.setFixedWidth(200)
            role_combo.setStyleSheet("font-size: 12px;")

            # Capture composite PK for handlers
            _cid = claim_id
            _did = doc_id
            _orig_role = role

            def _make_role_handler(cid_cap, did_cap, orig_role_cap, combo_cap):
                def handler(idx):
                    new_role = combo_cap.itemData(idx)
                    try:
                        c = get_connection()
                        with c:
                            c.execute(
                                "UPDATE claim_documents SET role=? "
                                "WHERE claim_id=? AND document_id=? AND role=?",
                                (new_role, cid_cap, did_cap, orig_role_cap),
                            )
                    except Exception:
                        pass
                return handler

            role_combo.currentIndexChanged.connect(
                _make_role_handler(_cid, _did, _orig_role, role_combo)
            )
            role_row.addWidget(role_combo)
            role_row.addStretch()

            # Remove button
            btn_remove = QPushButton("Remove")
            btn_remove.setFixedWidth(70)
            btn_remove.setStyleSheet(
                "font-size: 11px; padding: 2px 8px; color: #c0392b; "
                "border: 1px solid #c0392b; border-radius: 4px; background: white;"
            )

            def _make_remove_handler(cid_cap, did_cap, role_cap, card_cap):
                def handler():
                    try:
                        c = get_connection()
                        with c:
                            c.execute(
                                "DELETE FROM claim_documents "
                                "WHERE claim_id=? AND document_id=? AND role=?",
                                (cid_cap, did_cap, role_cap),
                            )
                        card_cap.setVisible(False)
                        card_cap.deleteLater()
                    except Exception:
                        pass
                return handler

            btn_remove.clicked.connect(_make_remove_handler(_cid, _did, _orig_role, card))
            role_row.addWidget(btn_remove)
            card_layout.addLayout(role_row)

            # Page evidence snippets
            if pages:
                for page_info in pages[:3]:  # show up to 3 pages per doc
                    pg_num = page_info.get("page_number", "?")
                    keyword = page_info.get("keyword", "")
                    snippet = page_info.get("snippet", "")[:300]
                    if snippet:
                        snippet_text = f"<i>Page {_html.escape(str(pg_num))}</i>"
                        if keyword:
                            snippet_text += f" &nbsp;·&nbsp; keyword: <b>{_html.escape(keyword)}</b>"
                        snippet_text += f"<br><span style='color:#444;font-size:11px;'>{_html.escape(snippet)}</span>"
                        snip_lbl = QLabel(snippet_text)
                        snip_lbl.setWordWrap(True)
                        snip_lbl.setStyleSheet(
                            "font-size: 12px; color: #333; padding: 4px 6px; "
                            "background: #fff; border-radius: 4px; "
                            "border: 1px solid #e0e0e0; margin-top: 2px;"
                        )
                        card_layout.addWidget(snip_lbl)
                if len(pages) > 3:
                    more_lbl = QLabel(f"  …and {len(pages) - 3} more page(s) matched")
                    more_lbl.setStyleSheet("font-size: 11px; color: #777; padding: 2px 4px;")
                    card_layout.addWidget(more_lbl)

            self._evidence_layout.addWidget(card)

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
        self._update_triangle_preview()
        self._update_risk_labels(claim)
        self._load_evidence(claim.id)

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

    def _clear_editor(self):
        self._current_claim_id = None
        self._claim_title.setText("Select or create a claim")
        self._condition_name.blockSignals(True)
        self._condition_name.setCurrentIndex(0)
        self._condition_name.blockSignals(False)
        for w in [self._vasrd_code, self._presumptive_basis,
                  self._diag_source, self._diag_date, self._insvc_source,
                  self._insvc_date, self._nexus_source, self._nexus_date]:
            w.clear()
        self._vasrd_hint.clear()
        self._insvc_description.clear()
        self._notes.clear()
        self._clear_evidence()
        for cb in [self._diag_checked, self._insvc_checked, self._nexus_checked,
                   self._nexus_verified]:
            cb.setChecked(False)
        self._priority_rating.setValue(0)
        self._body_system.setCurrentIndex(0)
        self._claim_type.setCurrentIndex(0)
        self._nexus_type_combo.setCurrentIndex(0)
        self._triangle.set_state(False, False, False)
        self._status_badge.setText("")
        self._btn_save.setEnabled(False)
        self._btn_delete_claim.setVisible(False)

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
