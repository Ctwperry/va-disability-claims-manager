"""
Veteran profile panel — create and edit veteran records.
"""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QLineEdit, QComboBox, QCheckBox, QTextEdit,
    QPushButton, QFrame, QScrollArea, QMessageBox,
    QSizePolicy, QSpacerItem
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont

from app.config import MILITARY_BRANCHES, SERVICE_ERAS, DISCHARGE_TYPES
from app.core.veteran import Veteran
import app.db.repositories.veteran_repo as veteran_repo


class VeteranPanel(QWidget):
    """Panel for viewing and editing a veteran's profile."""

    veteran_saved = pyqtSignal(int)   # emits veteran_id after save
    veteran_deleted = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._veteran_id: int | None = None
        self._build_ui()

    # ------------------------------------------------------------------
    # UI Construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 24, 24, 24)
        outer.setSpacing(0)

        # Header
        header_row = QHBoxLayout()
        title = QLabel("Veteran Profile")
        title.setObjectName("section_header")
        header_row.addWidget(title)
        header_row.addStretch()

        self._btn_new = QPushButton("+ New Veteran")
        self._btn_new.setObjectName("secondary_btn")
        self._btn_new.setFixedWidth(130)
        self._btn_new.clicked.connect(self._on_new)
        header_row.addWidget(self._btn_new)

        self._btn_delete = QPushButton("Delete")
        self._btn_delete.setObjectName("danger_btn")
        self._btn_delete.setFixedWidth(80)
        self._btn_delete.clicked.connect(self._on_delete)
        self._btn_delete.setVisible(False)
        header_row.addWidget(self._btn_delete)

        outer.addLayout(header_row)

        # Divider
        div = QFrame()
        div.setFrameShape(QFrame.Shape.HLine)
        div.setStyleSheet("color: #dde2e8; margin: 12px 0px;")
        outer.addWidget(div)

        # Scrollable form area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        form_container = QWidget()
        form_layout = QVBoxLayout(form_container)
        form_layout.setContentsMargins(0, 0, 16, 0)
        form_layout.setSpacing(16)

        # ---- Card: Personal Information ----
        form_layout.addWidget(self._make_card_header("Personal Information"))
        card1 = self._make_card()
        fl1 = QFormLayout(card1)
        fl1.setSpacing(10)
        fl1.setContentsMargins(16, 16, 16, 16)
        fl1.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self._name = QLineEdit()
        self._name.setPlaceholderText("Full legal name")
        fl1.addRow(self._lbl("Full Name *"), self._name)

        self._ssn = QLineEdit()
        self._ssn.setPlaceholderText("Last 4 digits only (e.g. 1234)")
        self._ssn.setMaxLength(4)
        self._ssn.setFixedWidth(120)
        fl1.addRow(self._lbl("SSN (Last 4)"), self._ssn)

        self._dob = QLineEdit()
        self._dob.setPlaceholderText("YYYY-MM-DD")
        self._dob.setFixedWidth(140)
        fl1.addRow(self._lbl("Date of Birth"), self._dob)

        form_layout.addWidget(card1)

        # ---- Card: Military Service ----
        form_layout.addWidget(self._make_card_header("Military Service"))
        card2 = self._make_card()
        fl2 = QFormLayout(card2)
        fl2.setSpacing(10)
        fl2.setContentsMargins(16, 16, 16, 16)
        fl2.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self._branch = QComboBox()
        self._branch.addItem("-- Select Branch --", "")
        for b in MILITARY_BRANCHES:
            self._branch.addItem(b, b)
        fl2.addRow(self._lbl("Branch *"), self._branch)

        self._era = QComboBox()
        self._era.addItem("-- Select Era --", "")
        for e in SERVICE_ERAS:
            self._era.addItem(e, e)
        fl2.addRow(self._lbl("Service Era"), self._era)

        entry_row = QHBoxLayout()
        self._entry_date = QLineEdit()
        self._entry_date.setPlaceholderText("YYYY-MM-DD")
        self._entry_date.setFixedWidth(140)
        entry_row.addWidget(self._entry_date)
        entry_row.addWidget(QLabel("  to  "))
        self._sep_date = QLineEdit()
        self._sep_date.setPlaceholderText("YYYY-MM-DD")
        self._sep_date.setFixedWidth(140)
        entry_row.addWidget(self._sep_date)
        entry_row.addStretch()
        fl2.addRow(self._lbl("Service Dates"), entry_row)

        self._discharge = QComboBox()
        for d in DISCHARGE_TYPES:
            self._discharge.addItem(d, d)
        fl2.addRow(self._lbl("Discharge Type"), self._discharge)

        self._dd214 = QCheckBox("DD-214 on file")
        fl2.addRow(self._lbl(""), self._dd214)

        form_layout.addWidget(card2)

        # ---- Card: Additional Notes ----
        form_layout.addWidget(self._make_card_header("Notes"))
        card3 = self._make_card()
        fl3 = QVBoxLayout(card3)
        fl3.setContentsMargins(16, 16, 16, 16)

        self._notes = QTextEdit()
        self._notes.setPlaceholderText(
            "Additional notes about this veteran's service history, "
            "known conditions, or claim strategy..."
        )
        self._notes.setMinimumHeight(100)
        self._notes.setMaximumHeight(180)
        fl3.addWidget(self._notes)

        form_layout.addWidget(card3)

        # Spacer + Save button
        form_layout.addItem(QSpacerItem(0, 12))

        save_row = QHBoxLayout()
        save_row.addStretch()
        self._btn_save = QPushButton("Save Profile")
        self._btn_save.setFixedWidth(140)
        self._btn_save.clicked.connect(self._on_save)
        save_row.addWidget(self._btn_save)
        form_layout.addLayout(save_row)

        form_layout.addStretch()

        scroll.setWidget(form_container)
        outer.addWidget(scroll)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load_veteran(self, veteran_id: int | None):
        """Load an existing veteran (or clear form if None)."""
        self._veteran_id = veteran_id
        if veteran_id is None:
            self._clear_form()
            self._btn_delete.setVisible(False)
            return

        v = veteran_repo.get_by_id(veteran_id)
        if v is None:
            self._clear_form()
            return

        self._name.setText(v.full_name)
        self._ssn.setText(v.ssn_last4)
        self._dob.setText(v.dob)
        self._set_combo(self._branch, v.branch)
        self._set_combo(self._era, v.era)
        self._entry_date.setText(v.entry_date)
        self._sep_date.setText(v.separation_date)
        self._set_combo(self._discharge, v.discharge_type)
        self._dd214.setChecked(v.dd214_on_file)
        self._notes.setPlainText(v.notes)
        self._btn_delete.setVisible(True)

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _on_save(self):
        name = self._name.text().strip()
        if not name:
            QMessageBox.warning(self, "Validation", "Full Name is required.")
            return

        v = Veteran(
            id=self._veteran_id,
            full_name=name,
            ssn_last4=self._ssn.text().strip(),
            dob=self._dob.text().strip(),
            branch=self._branch.currentData() or "",
            era=self._era.currentData() or "",
            entry_date=self._entry_date.text().strip(),
            separation_date=self._sep_date.text().strip(),
            discharge_type=self._discharge.currentData() or "Honorable",
            dd214_on_file=self._dd214.isChecked(),
            notes=self._notes.toPlainText().strip(),
        )

        if self._veteran_id is None:
            new_id = veteran_repo.create(v)
            self._veteran_id = new_id
            self._btn_delete.setVisible(True)
            self.veteran_saved.emit(new_id)
            QMessageBox.information(self, "Saved", f"Veteran '{name}' created successfully.")
        else:
            veteran_repo.update(v)
            self.veteran_saved.emit(self._veteran_id)
            QMessageBox.information(self, "Saved", f"Profile updated for '{name}'.")

    def _on_new(self):
        self._veteran_id = None
        self._clear_form()
        self._btn_delete.setVisible(False)
        self._name.setFocus()

    def _on_delete(self):
        if self._veteran_id is None:
            return
        v = veteran_repo.get_by_id(self._veteran_id)
        name = v.full_name if v else "this veteran"
        reply = QMessageBox.question(
            self, "Confirm Delete",
            f"Delete all data for {name}?\n\n"
            "This will permanently delete all claims, documents, and records. "
            "This cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            veteran_repo.delete(self._veteran_id)
            self._veteran_id = None
            self._clear_form()
            self._btn_delete.setVisible(False)
            self.veteran_deleted.emit()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _clear_form(self):
        for w in (self._name, self._ssn, self._dob, self._entry_date, self._sep_date):
            w.clear()
        self._branch.setCurrentIndex(0)
        self._era.setCurrentIndex(0)
        self._discharge.setCurrentIndex(0)
        self._dd214.setChecked(False)
        self._notes.clear()

    @staticmethod
    def _lbl(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setObjectName("field_label")
        lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        lbl.setMinimumWidth(120)
        return lbl

    @staticmethod
    def _make_card() -> QFrame:
        card = QFrame()
        card.setObjectName("card")
        return card

    @staticmethod
    def _make_card_header(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setObjectName("subsection_header")
        return lbl

    @staticmethod
    def _set_combo(combo: QComboBox, value: str):
        idx = combo.findData(value)
        if idx >= 0:
            combo.setCurrentIndex(idx)
        else:
            # Try matching display text
            idx = combo.findText(value)
            if idx >= 0:
                combo.setCurrentIndex(idx)
