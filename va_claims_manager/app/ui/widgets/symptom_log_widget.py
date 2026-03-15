"""
Symptom & Treatment Log widget — the "Evidence Map" table.

A standalone QWidget encapsulating the 5-column editable symptom log
used in the Claims panel. Data is serialised as JSON for DB persistence.

Public API:
    load_data(json_str: str)  — populate table from JSON string
    get_data_json() -> str    — serialise table rows to JSON string
    clear()                   — reset table to zero rows
"""
from __future__ import annotations
import json
from app.core.json_guard import parse_symptom_log

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
)


class SymptomLogWidget(QWidget):
    """Editable symptom & treatment log table with JSON serialisation."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        inst = QLabel(
            "Log each medical record entry that supports this claim. "
            "Reference the source document and page number so the VA rater can find it directly. "
            "This data auto-fills the Statement in Support of Claim (21-4138) generator."
        )
        inst.setWordWrap(True)
        inst.setStyleSheet("font-size: 11px; color: #666; margin-bottom: 4px;")
        layout.addWidget(inst)

        self._table = QTableWidget()
        self._table.setColumnCount(5)
        self._table.setHorizontalHeaderLabels([
            "Date", "Source & Page #", "Complaint / Symptom",
            "Diagnosis / Doctor's Notes", "Treatment / Limitations"
        ])
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        self._table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        self._table.setColumnWidth(0, 90)
        self._table.setColumnWidth(1, 130)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setAlternatingRowColors(True)
        self._table.setFixedHeight(160)
        self._table.setStyleSheet(
            "QTableWidget { font-size: 12px; }"
            "QHeaderView::section { font-size: 11px; font-weight: bold; "
            "padding: 3px 5px; }"
        )
        self._table.verticalHeader().setVisible(False)
        layout.addWidget(self._table)

        btn_row = QHBoxLayout()
        add_btn = QPushButton("+ Add Row")
        add_btn.setFixedHeight(26)
        add_btn.setFixedWidth(90)
        add_btn.clicked.connect(self._add_row)
        btn_row.addWidget(add_btn)

        del_btn = QPushButton("Delete Row")
        del_btn.setFixedHeight(26)
        del_btn.setFixedWidth(90)
        del_btn.clicked.connect(self._delete_row)
        btn_row.addWidget(del_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load_data(self, json_str: str):
        """Populate from a JSON string (list of entry dicts)."""
        self._table.setRowCount(0)
        entries = parse_symptom_log(json_str)
        for entry in entries:
            row = self._table.rowCount()
            self._table.insertRow(row)
            self._table.setItem(row, 0, QTableWidgetItem(entry.get("date", "")))
            self._table.setItem(row, 1, QTableWidgetItem(entry.get("source", "")))
            self._table.setItem(row, 2, QTableWidgetItem(entry.get("complaint", "")))
            self._table.setItem(row, 3, QTableWidgetItem(entry.get("diagnosis", "")))
            self._table.setItem(row, 4, QTableWidgetItem(entry.get("treatment", "")))
            self._table.setRowHeight(row, 28)

    def get_data_json(self) -> str:
        """Serialise table rows to a JSON string."""
        entries = []
        for row in range(self._table.rowCount()):
            def cell(c, r=row):
                item = self._table.item(r, c)
                return item.text().strip() if item else ""
            entries.append({
                "date": cell(0),
                "source": cell(1),
                "complaint": cell(2),
                "diagnosis": cell(3),
                "treatment": cell(4),
            })
        return json.dumps(entries, ensure_ascii=False)

    def clear(self):
        """Reset table to zero rows."""
        self._table.setRowCount(0)

    # ------------------------------------------------------------------
    # Private slots
    # ------------------------------------------------------------------

    def _add_row(self):
        row = self._table.rowCount()
        self._table.insertRow(row)
        for col in range(5):
            self._table.setItem(row, col, QTableWidgetItem(""))
        self._table.setRowHeight(row, 28)

    def _delete_row(self):
        selected = self._table.selectedItems()
        if selected:
            self._table.removeRow(self._table.currentRow())
