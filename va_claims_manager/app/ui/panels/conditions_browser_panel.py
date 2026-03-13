"""
Claimable Conditions Browser Panel.

Displays all 400+ VASRD diagnostic conditions organized by body system.
Features:
  - Real-time search by code or name
  - Filter by body system and claim status
  - Presumptive badge for PACT Act / Agent Orange conditions
  - One-click "Add Claim" to create a claim from any condition
"""
from __future__ import annotations

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QPushButton, QScrollArea, QLineEdit, QComboBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QSizePolicy,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont

from app.services.conditions_service import load_enriched_conditions
import app.db.repositories.claim_repo as claim_repo


class ConditionsBrowserPanel(QWidget):
    """Browse all claimable VA disability conditions with search and filters."""

    add_claim_requested = pyqtSignal(dict)  # emits enriched condition dict

    def __init__(self, parent=None):
        super().__init__(parent)
        self._veteran_id: int | None = None
        self._all_conditions: list[dict] = []
        self._claimed_names: set[str] = set()
        self._body_systems: list[str] = []
        self._build_ui()
        self._load_conditions()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load_veteran(self, veteran_id: int | None):
        self._veteran_id = veteran_id
        self._reload_claimed()
        self._apply_filters()

    # ------------------------------------------------------------------
    # Build UI
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
        title_lbl = QLabel("Claimable Conditions Browser")
        title_lbl.setStyleSheet("color: white; font-size: 17px; font-weight: bold;")
        hl.addWidget(title_lbl)
        sub_lbl = QLabel(
            "All VASRD diagnostic codes with PACT Act / presumptive eligibility indicators  ·  "
            "Click 'Add Claim' to start filing"
        )
        sub_lbl.setStyleSheet("color: #a8c4e0; font-size: 12px;")
        hl.addWidget(sub_lbl)
        outer.addWidget(header)

        # Filter / search bar
        filter_frame = QFrame()
        filter_frame.setStyleSheet(
            "background: #f8f9fb; border-bottom: 1px solid #dde2e8;"
        )
        filter_layout = QHBoxLayout(filter_frame)
        filter_layout.setContentsMargins(16, 10, 16, 10)
        filter_layout.setSpacing(12)

        search_lbl = QLabel("Search:")
        search_lbl.setStyleSheet("font-size: 12px;")
        filter_layout.addWidget(search_lbl)

        self._search_box = QLineEdit()
        self._search_box.setPlaceholderText("Condition name or VASRD code...")
        self._search_box.setFixedWidth(260)
        self._search_box.textChanged.connect(self._apply_filters)
        filter_layout.addWidget(self._search_box)

        sys_lbl = QLabel("Body System:")
        sys_lbl.setStyleSheet("font-size: 12px;")
        filter_layout.addWidget(sys_lbl)

        self._system_combo = QComboBox()
        self._system_combo.addItem("All Systems", "")
        self._system_combo.setFixedWidth(180)
        self._system_combo.currentIndexChanged.connect(self._apply_filters)
        filter_layout.addWidget(self._system_combo)

        status_lbl = QLabel("Status:")
        status_lbl.setStyleSheet("font-size: 12px;")
        filter_layout.addWidget(status_lbl)

        self._status_combo = QComboBox()
        for label, key in [
            ("All Conditions", "all"),
            ("Not Yet Claimed", "unclaimed"),
            ("Already Claimed", "claimed"),
            ("Presumptive Only", "presumptive"),
        ]:
            self._status_combo.addItem(label, key)
        self._status_combo.setFixedWidth(160)
        self._status_combo.currentIndexChanged.connect(self._apply_filters)
        filter_layout.addWidget(self._status_combo)

        filter_layout.addStretch()

        self._count_lbl = QLabel("")
        self._count_lbl.setStyleSheet("font-size: 11px; color: #777;")
        filter_layout.addWidget(self._count_lbl)

        outer.addWidget(filter_frame)

        # Legend
        legend = QFrame()
        legend.setStyleSheet("background: #f0f6ff; border-bottom: 1px solid #dde2e8;")
        leg_layout = QHBoxLayout(legend)
        leg_layout.setContentsMargins(16, 6, 16, 6)
        leg_layout.setSpacing(16)
        for text, bg, fg in [
            ("Presumptive (PACT/AO)", "#fff3e0", "#b8610a"),
            ("Already Claimed", "#e8f8f0", "#1a7a4a"),
            ("Normal Claim", "#f8f9fb", "#333"),
        ]:
            badge = QLabel(f"  {text}  ")
            badge.setStyleSheet(
                f"background: {bg}; color: {fg}; font-size: 11px; padding: 2px 8px; "
                f"border-radius: 10px; border: 1px solid #dde2e8;"
            )
            leg_layout.addWidget(badge)
        leg_layout.addStretch()
        outer.addWidget(legend)

        # Table
        self._table = QTableWidget()
        self._table.setColumnCount(6)
        self._table.setHorizontalHeaderLabels(
            ["Code", "Condition Name", "Body System", "Type", "Status", "Action"]
        )
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        self._table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        self._table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        self._table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.Fixed)
        self._table.setColumnWidth(0, 68)
        self._table.setColumnWidth(2, 155)
        self._table.setColumnWidth(3, 140)
        self._table.setColumnWidth(4, 100)
        self._table.setColumnWidth(5, 90)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setAlternatingRowColors(True)
        self._table.setStyleSheet(
            "QTableWidget { border: none; gridline-color: #ebebeb; font-size: 12px; }"
            "QTableWidget::item { padding: 4px 6px; }"
            "QHeaderView::section { background: #f5f7fa; border-bottom: 2px solid #dde2e8; "
            "font-weight: bold; font-size: 11px; color: #555e6e; padding: 4px 6px; }"
        )
        self._table.verticalHeader().setVisible(False)
        self._table.setShowGrid(True)
        self._table.setSortingEnabled(True)
        outer.addWidget(self._table, 1)

    # ------------------------------------------------------------------
    # Data loading
    # ------------------------------------------------------------------

    def _load_conditions(self):
        """Load VASRD codes enriched with presumptive data, populate table."""
        self._all_conditions = load_enriched_conditions()

        # Collect unique body systems
        systems = sorted(set(c.get("system", "Other") for c in self._all_conditions))
        self._body_systems = systems
        for s in systems:
            self._system_combo.addItem(s, s)

        self._populate_table()

    def _populate_table(self):
        """Build all table rows once. Filtering done via setRowHidden."""
        self._table.setSortingEnabled(False)
        self._table.setRowCount(len(self._all_conditions))

        for row, cond in enumerate(self._all_conditions):
            code = cond.get("code", "")
            name = cond.get("name", "")
            system = cond.get("system", "")
            is_presumptive = cond.get("is_presumptive", False)
            basis = cond.get("presumptive_basis", "")

            # Code
            code_item = QTableWidgetItem(code)
            code_item.setData(Qt.ItemDataRole.UserRole, cond)
            code_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            code_item.setFont(QFont("Consolas", 11))
            self._table.setItem(row, 0, code_item)

            # Name
            name_item = QTableWidgetItem(name)
            self._table.setItem(row, 1, name_item)

            # Body system
            sys_item = QTableWidgetItem(system)
            sys_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._table.setItem(row, 2, sys_item)

            # Type badge
            if is_presumptive:
                type_item = QTableWidgetItem("Presumptive")
                type_item.setForeground(QColor("#b8610a"))
                type_item.setBackground(QColor("#fff3e0"))
                type_item.setToolTip(basis)
            else:
                type_item = QTableWidgetItem("Standard")
                type_item.setForeground(QColor("#555e6e"))
            type_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._table.setItem(row, 3, type_item)

            # Status placeholder — updated in _reload_claimed
            status_item = QTableWidgetItem("—")
            status_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._table.setItem(row, 4, status_item)

            # Add Claim button
            add_btn = QPushButton("Add Claim")
            add_btn.setFixedHeight(26)
            add_btn.setStyleSheet(
                "QPushButton { font-size: 11px; padding: 1px 8px; "
                "background: #0070c0; color: white; border-radius: 4px; }"
                "QPushButton:hover { background: #005a9e; }"
                "QPushButton:disabled { background: #c0c0c0; color: #888; }"
            )
            add_btn.clicked.connect(self._make_add_handler(cond))
            self._table.setCellWidget(row, 5, add_btn)
            self._table.setRowHeight(row, 34)

        self._table.setSortingEnabled(True)
        self._reload_claimed()

    def _reload_claimed(self):
        """Refresh 'Status' column and button state based on current claims."""
        self._claimed_names = set()
        if self._veteran_id:
            for c in claim_repo.get_all(self._veteran_id):
                self._claimed_names.add(c.condition_name.lower())

        for row in range(self._table.rowCount()):
            code_item = self._table.item(row, 0)
            if not code_item:
                continue
            cond = code_item.data(Qt.ItemDataRole.UserRole)
            if not cond:
                continue
            name_lower = cond.get("name", "").lower()
            is_claimed = name_lower in self._claimed_names

            status_item = self._table.item(row, 4)
            if status_item:
                if is_claimed:
                    status_item.setText("Claimed")
                    status_item.setForeground(QColor("#1a7a4a"))
                    status_item.setBackground(QColor("#e8f8f0"))
                else:
                    status_item.setText("Not Claimed")
                    status_item.setForeground(QColor("#555e6e"))
                    status_item.setBackground(QColor("white"))

            add_btn = self._table.cellWidget(row, 5)
            if add_btn:
                add_btn.setEnabled(not is_claimed)
                add_btn.setText("Claimed" if is_claimed else "Add Claim")

        self._apply_filters()

    def _apply_filters(self):
        """Show/hide rows based on current search and filter values."""
        search = self._search_box.text().strip().lower()
        system_filter = self._system_combo.currentData() or ""
        status_filter = self._status_combo.currentData() or "all"

        visible = 0
        for row in range(self._table.rowCount()):
            code_item = self._table.item(row, 0)
            if not code_item:
                self._table.setRowHidden(row, True)
                continue

            cond = code_item.data(Qt.ItemDataRole.UserRole)
            if not cond:
                self._table.setRowHidden(row, True)
                continue

            code = cond.get("code", "").lower()
            name = cond.get("name", "").lower()
            system = cond.get("system", "")
            is_presumptive = cond.get("is_presumptive", False)
            is_claimed = name in self._claimed_names

            # Search filter
            if search and search not in code and search not in name:
                self._table.setRowHidden(row, True)
                continue

            # Body system filter
            if system_filter and system != system_filter:
                self._table.setRowHidden(row, True)
                continue

            # Status filter
            if status_filter == "claimed" and not is_claimed:
                self._table.setRowHidden(row, True)
                continue
            if status_filter == "unclaimed" and is_claimed:
                self._table.setRowHidden(row, True)
                continue
            if status_filter == "presumptive" and not is_presumptive:
                self._table.setRowHidden(row, True)
                continue

            self._table.setRowHidden(row, False)
            visible += 1

        total = self._table.rowCount()
        self._count_lbl.setText(f"Showing {visible} of {total} conditions")

    def _make_add_handler(self, cond: dict):
        def handler():
            self.add_claim_requested.emit(cond)
        return handler
