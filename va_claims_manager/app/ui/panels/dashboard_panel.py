"""
Dashboard panel: stat cards, combined rating, PACT Act eligibility banner.
"""
import json
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QPushButton, QScrollArea, QGridLayout, QGroupBox
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont

from app.config import PACT_ACT_PATH
from app.core.rating_calculator import combined_rating, rating_summary
import app.db.repositories.veteran_repo as veteran_repo
import app.db.repositories.claim_repo as claim_repo
import app.db.repositories.document_repo as doc_repo


class DashboardPanel(QWidget):
    navigate_to = pyqtSignal(str)   # emit panel key to navigate

    def __init__(self, parent=None):
        super().__init__(parent)
        self._veteran_id: int | None = None
        self._build_ui()

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(16)

        # Page title
        title = QLabel("Dashboard")
        title.setObjectName("section_header")
        layout.addWidget(title)

        # PACT Act banner (hidden by default)
        self._pact_banner = self._make_pact_banner()
        layout.addWidget(self._pact_banner)

        # Stat cards row
        cards_layout = QHBoxLayout()
        cards_layout.setSpacing(16)

        self._card_claims = StatCard("Claims", "0", "#0070c0", "Total disability claims")
        self._card_complete = StatCard("Complete", "0", "#1a7a4a", "Caluza Triangle fully documented")
        self._card_at_risk = StatCard("At Risk", "0", "#c0392b", "Claims with denial risk flags")
        self._card_docs = StatCard("Documents", "0", "#b8610a", "Indexed medical records")
        self._card_rating = StatCard("Est. Combined", "0%", "#003366", "Estimated combined rating")

        for card in [self._card_claims, self._card_complete, self._card_at_risk,
                     self._card_docs, self._card_rating]:
            cards_layout.addWidget(card)
        layout.addLayout(cards_layout)

        # Claims overview table
        layout.addWidget(self._section_lbl("Claims Overview"))
        self._claims_frame = QFrame()
        self._claims_frame.setObjectName("card")
        self._claims_inner = QVBoxLayout(self._claims_frame)
        self._claims_inner.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._claims_frame)

        # Combined rating detail
        layout.addWidget(self._section_lbl("Combined Rating Calculation  (VA Whole-Person Method)"))
        self._rating_detail = QLabel("")
        self._rating_detail.setWordWrap(True)
        self._rating_detail.setStyleSheet(
            "background:#ffffff; border:1px solid #dde2e8; border-radius:6px; "
            "padding:14px; font-family:Consolas,monospace; font-size:12px; color:#1a1a2e;"
        )
        layout.addWidget(self._rating_detail)

        layout.addStretch()
        scroll.setWidget(container)
        outer.addWidget(scroll)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load_veteran(self, veteran_id: int | None):
        self._veteran_id = veteran_id
        self._refresh()

    def refresh(self):
        self._refresh()

    # ------------------------------------------------------------------
    # Refresh
    # ------------------------------------------------------------------

    def _refresh(self):
        if not self._veteran_id:
            self._clear()
            return

        veteran = veteran_repo.get_by_id(self._veteran_id)
        if not veteran:
            self._clear()
            return

        claims = claim_repo.get_all(self._veteran_id)
        total_claims = len(claims)
        complete_claims = sum(1 for c in claims if c.triangle_complete)
        at_risk = sum(1 for c in claims if c.risk_count > 0)
        doc_count = doc_repo.count(self._veteran_id)

        # Estimated combined rating
        ratings = [c.priority_rating for c in claims if c.priority_rating and c.priority_rating > 0]
        est_combined = combined_rating(ratings) if ratings else 0

        # Update stat cards
        self._card_claims.set_value(str(total_claims))
        self._card_complete.set_value(str(complete_claims))
        self._card_at_risk.set_value(str(at_risk))
        self._card_docs.set_value(str(doc_count))
        self._card_rating.set_value(f"{est_combined}%")

        # PACT Act banner
        self._update_pact_banner(veteran)

        # Claims table
        self._rebuild_claims_table(claims)

        # Rating calculation detail
        if ratings:
            summary = rating_summary(ratings)
            lines = [f"Individual ratings (sorted): {summary['individual_ratings']}%"]
            for step in summary["steps"]:
                lines.append(
                    f"  Apply {step['rating']}% to {step['remaining_before']:.1f}% remaining  "
                    f"→ -{step['disability_applied']:.1f}%  "
                    f"→ {step['remaining_after']:.1f}% healthy remaining"
                )
            lines.append("")
            lines.append(f"Raw combined: {summary['raw_combined']}%")
            lines.append(f"Final (rounded to nearest 10): {summary['combined']}%")
            self._rating_detail.setText("\n".join(lines))
        else:
            self._rating_detail.setText(
                "No claims with estimated ratings yet.\n"
                "Add an estimated % to each claim in the Claims tab to see the combined calculation."
            )

    def _clear(self):
        for card in [self._card_claims, self._card_complete, self._card_at_risk,
                     self._card_docs, self._card_rating]:
            card.set_value("—")
        self._pact_banner.setVisible(False)
        self._rating_detail.setText("Select a veteran to see the dashboard.")
        self._clear_claims_table()

    def _rebuild_claims_table(self, claims):
        self._clear_claims_table()
        if not claims:
            empty = QLabel("  No claims yet. Go to the Claims tab to add your first claim.")
            empty.setStyleSheet("color: #555e6e; padding: 16px; font-size: 13px;")
            self._claims_inner.addWidget(empty)
            return

        # Header row
        header = self._table_row(
            ["Condition", "Code", "System", "Diagnosis", "In-Service", "Nexus", "Risk", "Est. %"],
            is_header=True
        )
        self._claims_inner.addWidget(header)

        for claim in claims:
            def check(val): return "✓" if val else "✗"
            risk_txt = f"{claim.risk_count} flag(s)" if claim.risk_count else "None"
            rating_txt = f"{claim.priority_rating}%" if claim.priority_rating else "—"
            row_widget = self._table_row([
                claim.condition_name,
                claim.vasrd_code or "—",
                claim.body_system or "—",
                check(claim.has_diagnosis),
                check(claim.has_inservice_event),
                check(claim.has_nexus),
                risk_txt,
                rating_txt,
            ], is_header=False, triangle_complete=claim.triangle_complete, risk_count=claim.risk_count)
            self._claims_inner.addWidget(row_widget)

    def _clear_claims_table(self):
        while self._claims_inner.count():
            item = self._claims_inner.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _update_pact_banner(self, veteran):
        era = veteran.era or ""
        show = False
        msg = ""

        if "Post-9/11" in era or "Gulf War" in era:
            show = True
            msg = (
                "PACT Act eligibility detected: This veteran's service era "
                "may qualify them for Burn Pit / Toxic Exposure presumptive conditions. "
                "Check the PACT Act presumptive list for applicable cancers and respiratory conditions."
            )
        elif "Vietnam" in era:
            show = True
            msg = (
                "Agent Orange eligibility detected: This veteran's Vietnam-era service "
                "may qualify them for Agent Orange presumptive conditions including "
                "Type 2 Diabetes, Ischemic Heart Disease, and various cancers. "
                "Hypertension and MGUS were also added under the PACT Act."
            )

        self._pact_banner.setVisible(show)
        if show:
            self._pact_banner.findChild(QLabel, "pact_msg").setText(msg)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _section_lbl(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setObjectName("subsection_header")
        return lbl

    @staticmethod
    def _make_pact_banner() -> QFrame:
        frame = QFrame()
        frame.setObjectName("card")
        frame.setStyleSheet(
            "QFrame#card { background-color: #fff8e1; border: 1px solid #ffc107; border-radius: 8px; }"
        )
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(14, 10, 14, 10)

        icon = QLabel("⚠")
        icon.setStyleSheet("font-size: 20px; color: #b8610a;")
        layout.addWidget(icon)

        msg = QLabel("")
        msg.setObjectName("pact_msg")
        msg.setWordWrap(True)
        msg.setStyleSheet("color: #5d4037; font-size: 12px; background: transparent;")
        layout.addWidget(msg)

        frame.setVisible(False)
        return frame

    @staticmethod
    def _table_row(cols: list[str], is_header: bool,
                   triangle_complete: bool = False, risk_count: int = 0) -> QWidget:
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(14, 6, 14, 6)
        layout.setSpacing(0)

        widths = [None, 60, 120, 80, 80, 60, 70, 60]  # None = stretch

        if is_header:
            row.setStyleSheet("background-color: #f5f7fa; border-bottom: 2px solid #dde2e8;")

        for i, (text, width) in enumerate(zip(cols, widths)):
            lbl = QLabel(text)
            if is_header:
                lbl.setStyleSheet("font-weight: bold; font-size: 11px; color: #555e6e;")
            else:
                # Color checkmarks
                if text == "✓":
                    lbl.setStyleSheet("color: #1a7a4a; font-weight: bold;")
                elif text == "✗":
                    lbl.setStyleSheet("color: #c0392b; font-weight: bold;")
                elif i == 0 and triangle_complete:
                    lbl.setStyleSheet("color: #1a7a4a; font-weight: 500;")
                elif i == 6 and risk_count > 0:
                    lbl.setStyleSheet("color: #c0392b; font-weight: bold;")

            if width:
                lbl.setFixedWidth(width)
                lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            else:
                lbl.setSizePolicy(lbl.sizePolicy().horizontalPolicy(), lbl.sizePolicy().verticalPolicy())

            layout.addWidget(lbl)

        if not is_header:
            row.setStyleSheet(
                "QWidget:hover { background-color: #f5f7fa; }"
                "border-bottom: 1px solid #f0f2f5;"
            )

        return row


class StatCard(QFrame):
    """A colored stat card for the dashboard."""

    def __init__(self, label: str, value: str, color: str, tooltip: str = "", parent=None):
        super().__init__(parent)
        self.setObjectName("card")
        self.setToolTip(tooltip)
        self.setMinimumWidth(140)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(4)

        self._value_lbl = QLabel(value)
        self._value_lbl.setStyleSheet(
            f"font-size: 28px; font-weight: bold; color: {color};"
        )
        layout.addWidget(self._value_lbl)

        lbl = QLabel(label)
        lbl.setStyleSheet("font-size: 12px; color: #555e6e;")
        layout.addWidget(lbl)

        # Color accent bar at bottom
        bar = QFrame()
        bar.setFixedHeight(4)
        bar.setStyleSheet(f"background-color: {color}; border-radius: 2px;")
        layout.addWidget(bar)

    def set_value(self, value: str):
        self._value_lbl.setText(value)
