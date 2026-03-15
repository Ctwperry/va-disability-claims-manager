"""
Dashboard panel: stat cards, combined rating, PACT Act eligibility banner,
and what-if rating impact estimator.
"""
import json
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QPushButton, QScrollArea, QGridLayout, QGroupBox, QSpinBox
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont

from app.config import PACT_ACT_PATH
from app.core.rating_calculator import combined_rating, rating_summary, check_tdiu_eligibility
from app.analysis.presumptive_data import get_era_categories
from app.services.benefits_service import get_benefits_by_category
import app.db.repositories.veteran_repo as veteran_repo
import app.db.repositories.claim_repo as claim_repo
import app.db.repositories.document_repo as doc_repo

# 2025 VA monthly compensation rates (no dependents)
_VA_RATES_2025 = {
    0: 0, 10: 175.51, 20: 346.95, 30: 537.42, 40: 774.16,
    50: 1102.04, 60: 1395.93, 70: 1759.72, 80: 2044.89,
    90: 2297.96, 100: 3831.30,
}

# 2025 dependent add-on amounts (per month) by rating and family status.
# Rates apply at 30%+. Keys: (rating, spouse, children, parents)
# Rather than enumerate every combo, store the add-on components separately
# and sum them. Source: 38 CFR Part 3 / VA compensation rate tables.
_SPOUSE_ADDON = {
    30: 59, 40: 79, 50: 100, 60: 119, 70: 140, 80: 159, 90: 179, 100: 199,
}
_CHILD_ADDON = {
    30: 30, 40: 40, 50: 50, 60: 60, 70: 70, 80: 80, 90: 90, 100: 100,
}
_PARENT_ADDON = {
    30: 35, 40: 47, 50: 58, 60: 70, 70: 81, 80: 92, 90: 104, 100: 115,
}
_AID_ATTENDANCE_SPOUSE_ADDON = {
    30: 55, 40: 73, 50: 91, 60: 110, 70: 127, 80: 145, 90: 163, 100: 181,
}


def _monthly_compensation(rating: int, spouse: int, children: int, parents: int,
                           aid_attendance: bool = False) -> float:
    """Calculate estimated monthly VA compensation with dependents."""
    base = _VA_RATES_2025.get(rating, 0)
    if rating < 30:
        return base  # Dependents add-on starts at 30%
    spouse_add = (_AID_ATTENDANCE_SPOUSE_ADDON if aid_attendance else _SPOUSE_ADDON).get(rating, 0) * min(spouse, 1)
    child_add = _CHILD_ADDON.get(rating, 0) * children
    parent_add = _PARENT_ADDON.get(rating, 0) * min(parents, 2)
    return base + spouse_add + child_add + parent_add


class DashboardPanel(QWidget):
    navigate_to = pyqtSignal(str)          # emit panel key to navigate
    add_claim_requested = pyqtSignal(dict)  # condition dict from era recommendations

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

        # TDIU eligibility banner (hidden by default)
        self._tdiu_banner = self._make_tdiu_banner()
        layout.addWidget(self._tdiu_banner)

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
        rating_frame = QFrame()
        rating_frame.setObjectName("card")
        rating_fl = QVBoxLayout(rating_frame)
        rating_fl.setContentsMargins(14, 12, 14, 12)
        self._rating_detail = QLabel("")
        self._rating_detail.setWordWrap(True)
        self._rating_detail.setStyleSheet(
            "font-family:Consolas,monospace; font-size:12px;"
        )
        rating_fl.addWidget(self._rating_detail)
        layout.addWidget(rating_frame)

        # What-If Rating Estimator
        layout.addWidget(self._section_lbl("Rating Impact Estimator  (What-If Calculator)"))
        self._whatif_frame = self._build_whatif_widget()
        layout.addWidget(self._whatif_frame)

        # Federal Benefits section (hidden until veteran loaded)
        self._benefits_section_lbl = self._section_lbl("Federal Benefits at Your Rating")
        self._benefits_section_lbl.setVisible(False)
        layout.addWidget(self._benefits_section_lbl)

        self._benefits_frame = QFrame()
        self._benefits_frame.setObjectName("card")
        self._benefits_inner = QVBoxLayout(self._benefits_frame)
        self._benefits_inner.setContentsMargins(16, 12, 16, 14)
        self._benefits_inner.setSpacing(4)
        self._benefits_frame.setVisible(False)
        layout.addWidget(self._benefits_frame)

        # Service Era Presumptive Recommendations (hidden until veteran loaded)
        self._era_rec_section_lbl = self._section_lbl(
            "Service Era Presumptive Conditions  (Suggested Claims)"
        )
        self._era_rec_section_lbl.setVisible(False)
        layout.addWidget(self._era_rec_section_lbl)

        self._era_rec_frame = QFrame()
        self._era_rec_frame.setObjectName("card")
        self._era_rec_inner = QVBoxLayout(self._era_rec_frame)
        self._era_rec_inner.setContentsMargins(16, 12, 16, 12)
        self._era_rec_inner.setSpacing(6)
        self._era_rec_frame.setVisible(False)
        layout.addWidget(self._era_rec_frame)

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

        # TDIU eligibility check
        tdiu_result = check_tdiu_eligibility(ratings)
        self._update_tdiu_banner_result(tdiu_result)

        # Federal benefits section
        self._rebuild_benefits_section(est_combined, tdiu_result["eligible"])

        # Service era presumptive recommendations
        self._update_era_recommendations(veteran)

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

        # Update what-if estimator base ratings + family status
        self._whatif_update_base(ratings, veteran)

    # ------------------------------------------------------------------
    # What-If Rating Estimator
    # ------------------------------------------------------------------

    def _build_whatif_widget(self) -> QFrame:
        frame = QFrame()
        frame.setObjectName("card")
        outer = QVBoxLayout(frame)
        outer.setContentsMargins(16, 14, 16, 14)
        outer.setSpacing(10)

        # Description
        desc = QLabel(
            "See how adding a new claim changes your combined rating and monthly compensation. "
            "Rates shown are 2025 VA rates. Adjust family status below for dependent add-ons (30%+)."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #555e6e; font-size: 12px;")
        outer.addWidget(desc)

        # Current ratings row (populated on refresh)
        self._whatif_current_lbl = QLabel("Current ratings: —")
        self._whatif_current_lbl.setStyleSheet("font-size: 12px; color: #333;")
        outer.addWidget(self._whatif_current_lbl)

        # Add hypothetical rating row
        add_row = QHBoxLayout()
        add_row.addWidget(QLabel("Add hypothetical rating:"))
        self._whatif_spinbox = QSpinBox()
        self._whatif_spinbox.setRange(0, 100)
        self._whatif_spinbox.setSingleStep(10)
        self._whatif_spinbox.setValue(30)
        self._whatif_spinbox.setSuffix("%")
        self._whatif_spinbox.setFixedWidth(80)
        add_row.addWidget(self._whatif_spinbox)

        btn_add = QPushButton("+ Add")
        btn_add.setFixedWidth(70)
        btn_add.clicked.connect(self._whatif_add)
        add_row.addWidget(btn_add)

        btn_clear = QPushButton("Clear All")
        btn_clear.setFixedWidth(80)
        btn_clear.clicked.connect(self._whatif_clear)
        add_row.addWidget(btn_clear)
        add_row.addStretch()
        outer.addLayout(add_row)

        # Hypothetical ratings chips area
        self._whatif_chips_layout = QHBoxLayout()
        self._whatif_chips_layout.setSpacing(6)
        self._whatif_chips_layout.addStretch()
        outer.addLayout(self._whatif_chips_layout)

        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: #dde2e8;")
        outer.addWidget(sep)

        # Results area
        results_row = QHBoxLayout()
        results_row.setSpacing(24)

        # Before column
        before_col = QVBoxLayout()
        before_lbl = QLabel("Current")
        before_lbl.setStyleSheet("font-size: 11px; color: #888; font-weight: bold; text-transform: uppercase;")
        before_col.addWidget(before_lbl)
        self._whatif_before_rating = QLabel("0%")
        self._whatif_before_rating.setStyleSheet("font-size: 32px; font-weight: bold; color: #003366;")
        before_col.addWidget(self._whatif_before_rating)
        self._whatif_before_pay = QLabel("$0 / mo")
        self._whatif_before_pay.setStyleSheet("font-size: 13px; color: #555;")
        before_col.addWidget(self._whatif_before_pay)
        results_row.addLayout(before_col)

        # Arrow
        arrow_lbl = QLabel("→")
        arrow_lbl.setStyleSheet("font-size: 28px; color: #aaa;")
        arrow_lbl.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        results_row.addWidget(arrow_lbl)

        # After column
        after_col = QVBoxLayout()
        after_lbl = QLabel("With New Claim(s)")
        after_lbl.setStyleSheet("font-size: 11px; color: #888; font-weight: bold;")
        after_col.addWidget(after_lbl)
        self._whatif_after_rating = QLabel("0%")
        self._whatif_after_rating.setStyleSheet("font-size: 32px; font-weight: bold; color: #1a7a4a;")
        after_col.addWidget(self._whatif_after_rating)
        self._whatif_after_pay = QLabel("$0 / mo")
        self._whatif_after_pay.setStyleSheet("font-size: 13px; color: #555;")
        after_col.addWidget(self._whatif_after_pay)
        results_row.addLayout(after_col)

        # Delta column
        delta_col = QVBoxLayout()
        delta_lbl = QLabel("Difference")
        delta_lbl.setStyleSheet("font-size: 11px; color: #888; font-weight: bold;")
        delta_col.addWidget(delta_lbl)
        self._whatif_delta_rating = QLabel("+0%")
        self._whatif_delta_rating.setStyleSheet("font-size: 32px; font-weight: bold; color: #b8610a;")
        delta_col.addWidget(self._whatif_delta_rating)
        self._whatif_delta_pay = QLabel("+$0 / mo")
        self._whatif_delta_pay.setStyleSheet("font-size: 13px; color: #555;")
        delta_col.addWidget(self._whatif_delta_pay)
        results_row.addLayout(delta_col)

        results_row.addStretch()
        outer.addLayout(results_row)

        # Explanation text
        self._whatif_explanation = QLabel("")
        self._whatif_explanation.setWordWrap(True)
        self._whatif_explanation.setStyleSheet(
            "font-size: 11px; color: #555e6e; font-family: Consolas, monospace;"
        )
        outer.addWidget(self._whatif_explanation)

        # Family status row (affects compensation display)
        sep2 = QFrame()
        sep2.setFrameShape(QFrame.Shape.HLine)
        sep2.setStyleSheet("color: #dde2e8;")
        outer.addWidget(sep2)

        family_row = QHBoxLayout()
        family_row.setSpacing(16)
        family_row.addWidget(QLabel("Family status:"))

        family_row.addWidget(QLabel("Spouse:"))
        self._whatif_spouse = QSpinBox()
        self._whatif_spouse.setRange(0, 1)
        self._whatif_spouse.setFixedWidth(55)
        self._whatif_spouse.valueChanged.connect(self._whatif_recalculate)
        family_row.addWidget(self._whatif_spouse)

        family_row.addWidget(QLabel("Children:"))
        self._whatif_children = QSpinBox()
        self._whatif_children.setRange(0, 20)
        self._whatif_children.setFixedWidth(55)
        self._whatif_children.valueChanged.connect(self._whatif_recalculate)
        family_row.addWidget(self._whatif_children)

        family_row.addWidget(QLabel("Parents:"))
        self._whatif_parents = QSpinBox()
        self._whatif_parents.setRange(0, 2)
        self._whatif_parents.setFixedWidth(55)
        self._whatif_parents.valueChanged.connect(self._whatif_recalculate)
        family_row.addWidget(self._whatif_parents)

        family_note = QLabel("(pre-filled from veteran profile)")
        family_note.setStyleSheet("color: #888; font-size: 11px;")
        family_row.addWidget(family_note)
        family_row.addStretch()
        outer.addLayout(family_row)

        # Store state
        self._whatif_extra_ratings: list[int] = []
        self._whatif_base_ratings: list[int] = []

        return frame

    def _whatif_add(self):
        val = self._whatif_spinbox.value()
        if val <= 0:
            return
        self._whatif_extra_ratings.append(val)
        self._whatif_rebuild_chips()
        self._whatif_recalculate()

    def _whatif_clear(self):
        self._whatif_extra_ratings.clear()
        self._whatif_rebuild_chips()
        self._whatif_recalculate()

    def _whatif_rebuild_chips(self):
        """Rebuild the row of removable chip buttons for added ratings."""
        # Clear existing chips (everything except the trailing stretch)
        while self._whatif_chips_layout.count() > 1:
            item = self._whatif_chips_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        for i, rating in enumerate(self._whatif_extra_ratings):
            def _make_remove(idx):
                def _remove():
                    self._whatif_extra_ratings.pop(idx)
                    self._whatif_rebuild_chips()
                    self._whatif_recalculate()
                return _remove

            chip = QPushButton(f"  +{rating}%  ✕")
            chip.setStyleSheet(
                "QPushButton { background: #e3f0ff; color: #003d80; border: 1px solid #90c0f0; "
                "border-radius: 12px; font-size: 12px; padding: 2px 8px; }"
                "QPushButton:hover { background: #ffebee; color: #c0392b; border-color: #f0a0a0; }"
            )
            chip.clicked.connect(_make_remove(i))
            self._whatif_chips_layout.insertWidget(i, chip)

    def _whatif_recalculate(self):
        """Recompute before/after combined ratings and update labels."""
        base = self._whatif_base_ratings
        combined_before = combined_rating(base) if base else 0
        combined_after = combined_rating(base + self._whatif_extra_ratings) if (
            base or self._whatif_extra_ratings
        ) else 0

        spouse = self._whatif_spouse.value()
        children = self._whatif_children.value()
        parents = self._whatif_parents.value()
        pay_before = _monthly_compensation(combined_before, spouse, children, parents)
        pay_after = _monthly_compensation(combined_after, spouse, children, parents)
        delta_rating = combined_after - combined_before
        delta_pay = pay_after - pay_before

        self._whatif_before_rating.setText(f"{combined_before}%")
        self._whatif_after_rating.setText(f"{combined_after}%")
        self._whatif_before_pay.setText(f"${pay_before:,.2f} / mo")
        self._whatif_after_pay.setText(f"${pay_after:,.2f} / mo")

        sign = "+" if delta_rating >= 0 else ""
        self._whatif_delta_rating.setText(f"{sign}{delta_rating}%")
        pay_sign = "+" if delta_pay >= 0 else ""
        self._whatif_delta_pay.setText(f"{pay_sign}${delta_pay:,.2f} / mo")

        # Color delta
        delta_color = "#1a7a4a" if delta_rating > 0 else "#888"
        self._whatif_delta_rating.setStyleSheet(
            f"font-size: 32px; font-weight: bold; color: {delta_color};"
        )
        self._whatif_delta_pay.setStyleSheet(
            f"font-size: 13px; color: {delta_color};"
        )

        # Build step-by-step explanation
        if self._whatif_extra_ratings:
            all_ratings = sorted(base + self._whatif_extra_ratings, reverse=True)
            lines = [f"VA Whole-Person calculation with added ratings:"]
            remaining = 100.0
            for r in all_ratings:
                d = remaining * (r / 100.0)
                lines.append(
                    f"  Apply {r}% to {remaining:.1f}% remaining → -{d:.1f}% → {remaining - d:.1f}% healthy"
                )
                remaining -= d
            raw = round(100.0 - remaining)
            lines.append(f"  Raw: {raw}%  →  Rounded to nearest 10: {combined_after}%")
            self._whatif_explanation.setText("\n".join(lines))
        else:
            self._whatif_explanation.setText("")

    def _whatif_update_base(self, ratings: list[int], veteran=None):
        """Called on refresh to sync base ratings and veteran dependents."""
        self._whatif_base_ratings = ratings
        if ratings:
            self._whatif_current_lbl.setText(
                f"Current claim ratings: {', '.join(str(r) + '%' for r in sorted(ratings, reverse=True))}"
            )
        else:
            self._whatif_current_lbl.setText("Current claim ratings: none set yet")
        # Pre-fill family status from veteran profile
        if veteran is not None:
            self._whatif_spouse.blockSignals(True)
            self._whatif_children.blockSignals(True)
            self._whatif_parents.blockSignals(True)
            self._whatif_spouse.setValue(veteran.dependents_spouse)
            self._whatif_children.setValue(veteran.dependents_children)
            self._whatif_parents.setValue(veteran.dependents_parents)
            self._whatif_spouse.blockSignals(False)
            self._whatif_children.blockSignals(False)
            self._whatif_parents.blockSignals(False)
        self._whatif_recalculate()

    def _clear(self):
        for card in [self._card_claims, self._card_complete, self._card_at_risk,
                     self._card_docs, self._card_rating]:
            card.set_value("—")
        self._pact_banner.setVisible(False)
        self._tdiu_banner.setVisible(False)
        self._benefits_section_lbl.setVisible(False)
        self._benefits_frame.setVisible(False)
        self._era_rec_section_lbl.setVisible(False)
        self._era_rec_frame.setVisible(False)
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

    def _update_era_recommendations(self, veteran):
        """Rebuild the service-era presumptive suggestions panel."""
        # Clear previous content
        while self._era_rec_inner.count():
            item = self._era_rec_inner.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        era = veteran.era or ""
        categories = get_era_categories(era)

        if not categories:
            self._era_rec_section_lbl.setVisible(False)
            self._era_rec_frame.setVisible(False)
            return

        self._era_rec_section_lbl.setVisible(True)
        self._era_rec_frame.setVisible(True)

        intro = QLabel(
            f"Based on service era <b>{era}</b>, the following presumptive conditions may apply. "
            "Click <b>Add Claim</b> to pre-fill the Claims tab for any condition."
        )
        intro.setWordWrap(True)
        intro.setStyleSheet("color: #555e6e; font-size: 12px; margin-bottom: 4px;")
        self._era_rec_inner.addWidget(intro)

        for cat in categories:
            cat_lbl = QLabel(cat["label"])
            cat_lbl.setStyleSheet(
                "font-weight: bold; font-size: 12px; color: #1a3a5c; "
                "margin-top: 8px; margin-bottom: 2px;"
            )
            self._era_rec_inner.addWidget(cat_lbl)

            for cond_name in cat["conditions"]:
                row_widget = QWidget()
                row = QHBoxLayout(row_widget)
                row.setContentsMargins(8, 2, 0, 2)
                row.setSpacing(8)

                name_lbl = QLabel(cond_name)
                name_lbl.setStyleSheet("font-size: 12px; color: #333;")
                row.addWidget(name_lbl)
                row.addStretch()

                add_btn = QPushButton("Add Claim")
                add_btn.setFixedHeight(24)
                add_btn.setFixedWidth(80)
                add_btn.setStyleSheet(
                    "QPushButton { font-size: 11px; background: #0070c0; color: white; "
                    "border-radius: 4px; padding: 1px 6px; }"
                    "QPushButton:hover { background: #005a9e; }"
                )
                cond_dict = {
                    "name": cond_name,
                    "code": "",
                    "system": "",
                    "is_presumptive": True,
                    "presumptive_basis": cat["label"],
                    "eligible_eras": cat["eligible_eras"],
                }
                add_btn.clicked.connect(self._make_era_add_handler(cond_dict))
                row.addWidget(add_btn)

                self._era_rec_inner.addWidget(row_widget)

    def _make_era_add_handler(self, cond_dict: dict):
        def handler():
            self.add_claim_requested.emit(cond_dict)
        return handler

    def _rebuild_benefits_section(self, rating: int, tdiu_eligible: bool):
        """Rebuild the Federal Benefits section for the current combined rating."""
        # Clear existing content
        while self._benefits_inner.count():
            item = self._benefits_inner.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if rating == 0 and not tdiu_eligible:
            self._benefits_section_lbl.setVisible(False)
            self._benefits_frame.setVisible(False)
            return

        self._benefits_section_lbl.setVisible(True)
        self._benefits_frame.setVisible(True)

        effective = 100 if tdiu_eligible else rating
        label_text = (
            f"All benefits available at {effective}% (TDIU — paid at 100% rate)"
            if tdiu_eligible else
            f"All benefits available at {rating}%  (cumulative — includes every tier from 0%–{rating}%)"
        )
        intro = QLabel(label_text)
        intro.setWordWrap(True)
        intro.setStyleSheet("color: #555e6e; font-size: 12px; margin-bottom: 6px;")
        self._benefits_inner.addWidget(intro)

        grouped = get_benefits_by_category(rating, tdiu_eligible)
        if not grouped:
            self._benefits_inner.addWidget(QLabel("No benefits data available."))
            return

        CATEGORY_COLORS = {
            "Healthcare":            "#0070c0",
            "Employment":            "#1a7a4a",
            "Financial":             "#b8610a",
            "Education":             "#6b21a8",
            "Housing":               "#0e7490",
            "Insurance / Dependents":"#be123c",
            "Military Access":       "#374151",
        }

        for cat_label, items in grouped.items():
            color = CATEGORY_COLORS.get(cat_label, "#333")

            cat_header = QLabel(f"  {cat_label}  ({len(items)})")
            cat_header.setStyleSheet(
                f"font-weight: bold; font-size: 12px; color: white; "
                f"background-color: {color}; padding: 4px 8px; border-radius: 3px; "
                f"margin-top: 8px;"
            )
            self._benefits_inner.addWidget(cat_header)

            for benefit in items:
                row_widget = QWidget()
                row = QHBoxLayout(row_widget)
                row.setContentsMargins(10, 2, 4, 2)
                row.setSpacing(6)

                # Threshold badge
                badge = QLabel(f"{benefit['threshold']}%+")
                badge.setFixedWidth(38)
                badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
                badge.setStyleSheet(
                    f"font-size: 10px; font-weight: bold; color: {color}; "
                    f"border: 1px solid {color}; border-radius: 3px; padding: 1px 3px;"
                )
                row.addWidget(badge)

                # Name + detail
                text_col = QVBoxLayout()
                text_col.setSpacing(0)
                name_lbl = QLabel(benefit["name"])
                name_lbl.setWordWrap(True)
                name_lbl.setStyleSheet("font-size: 12px; color: #1a2332;")
                text_col.addWidget(name_lbl)
                detail_lbl = QLabel(benefit["detail"])
                detail_lbl.setWordWrap(True)
                detail_lbl.setStyleSheet("font-size: 11px; color: #555e6e;")
                text_col.addWidget(detail_lbl)
                row.addLayout(text_col, 1)

                self._benefits_inner.addWidget(row_widget)

    def _update_tdiu_banner(self, ratings: list[int]):
        """Show TDIU eligibility banner if individual ratings meet criteria."""
        result = check_tdiu_eligibility(ratings)
        self._update_tdiu_banner_result(result)

    def _update_tdiu_banner_result(self, result: dict):
        """Apply a pre-computed TDIU result dict to the banner."""
        self._tdiu_banner.setVisible(result["eligible"])
        if result["eligible"]:
            msg_lbl = self._tdiu_banner.findChild(QLabel, "tdiu_msg")
            if msg_lbl:
                msg_lbl.setText(result["reason"])

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _section_lbl(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setObjectName("subsection_header")
        return lbl

    @staticmethod
    def _make_tdiu_banner() -> QFrame:
        frame = QFrame()
        frame.setObjectName("banner_success")
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(14, 10, 14, 10)

        icon = QLabel("★")
        icon.setStyleSheet("font-size: 20px; color: #1a7a4a;")
        layout.addWidget(icon)

        text_col = QVBoxLayout()
        header_lbl = QLabel("TDIU Eligibility Detected  (Total Disability / Individual Unemployability)")
        header_lbl.setStyleSheet("color: #1a4a2a; font-weight: bold; font-size: 13px; background: transparent;")
        text_col.addWidget(header_lbl)

        msg = QLabel("")
        msg.setObjectName("tdiu_msg")
        msg.setWordWrap(True)
        msg.setStyleSheet("color: #2e7d32; font-size: 12px; background: transparent;")
        text_col.addWidget(msg)

        forms_lbl = QLabel(
            "Required forms:  <b>VA Form 21-8940</b> (Unemployability Application)  ·  "
            "<b>VA Form 21-4192</b> (Employment Verification from last employer)"
        )
        forms_lbl.setWordWrap(True)
        forms_lbl.setStyleSheet("color: #1a4a2a; font-size: 11px; background: transparent;")
        text_col.addWidget(forms_lbl)

        layout.addLayout(text_col)
        frame.setVisible(False)
        return frame

    @staticmethod
    def _make_pact_banner() -> QFrame:
        frame = QFrame()
        frame.setObjectName("banner_warning")
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
            row.setObjectName("table_header_row")

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
