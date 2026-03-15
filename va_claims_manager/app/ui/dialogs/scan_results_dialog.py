"""
Medical Record Analysis — Scan Results Dialog.

Displays potential disability conditions found in a veteran's indexed documents,
lets the veteran review evidence with context-analysis indicators, and creates
draft claims with one click.

Confidence levels (from context-aware weighted scoring):
  High      ≥ 0.70 — Strong positive evidence across quality sources
  Medium    ≥ 0.40 — Moderate positive evidence
  Low       ≥ 0.10 — Weak positive evidence
  Very Low  ≥ −0.10 — Mostly bare mentions, uncertain language
  Negative  < −0.10 — Evidence is dominated by negations/family history
                       (shown in "Excluded" filter tab, unchecked by default)
"""
from __future__ import annotations

import logging
from typing import Callable

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QFrame, QWidget, QCheckBox, QButtonGroup,
    QProgressBar, QSizePolicy, QMessageBox, QTextEdit
)
from PyQt6.QtCore import Qt, QRunnable, QObject, pyqtSignal, pyqtSlot, QTimer
from PyQt6.QtGui import QFont, QColor

from app.ui.workers import get_thread_pool

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Background scan worker
# ---------------------------------------------------------------------------

class _ScanSignals(QObject):
    progress = pyqtSignal(int, int, str)
    finished = pyqtSignal(list, int, int)   # (claims, doc_count, page_count)
    error    = pyqtSignal(str)


class _ScanWorker(QRunnable):
    def __init__(self, veteran_id: int, existing_condition_names: set[str]):
        super().__init__()
        self.veteran_id = veteran_id
        self.existing_condition_names = existing_condition_names
        self.signals = _ScanSignals()
        self.setAutoDelete(True)

    @pyqtSlot()
    def run(self):
        try:
            from app.analysis.condition_scanner import scan_veteran_records
            results, doc_count, page_count = scan_veteran_records(
                self.veteran_id,
                self.existing_condition_names,
                progress_cb=lambda c, t, m: self.signals.progress.emit(c, t, m),
            )
            self.signals.finished.emit(results, doc_count, page_count)
        except Exception:
            import traceback
            self.signals.error.emit(traceback.format_exc())


# ---------------------------------------------------------------------------
# Individual condition card widget
# ---------------------------------------------------------------------------

class _ConditionCard(QFrame):
    def __init__(self, claim, parent=None):
        super().__init__(parent)
        from app.analysis.condition_scanner import PotentialClaim
        self._claim: PotentialClaim = claim
        self._evidence_visible = False
        self._build_ui()

    def _build_ui(self):
        self.setObjectName("card")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(14, 10, 14, 10)
        outer.setSpacing(6)

        # --- Header row ---
        hdr = QHBoxLayout()
        hdr.setSpacing(8)

        is_negative = self._claim.confidence == "Negative"

        self._checkbox = QCheckBox()
        # Auto-check High and Medium; leave Low/VeryLow/Negative unchecked
        default_checked = (
            self._claim.confidence in ("High", "Medium")
            and not self._claim.already_claimed
            and not is_negative
        )
        self._checkbox.setChecked(default_checked)
        self._checkbox.setEnabled(not self._claim.already_claimed and not is_negative)
        hdr.addWidget(self._checkbox)

        # Condition name
        name_lbl = QLabel(self._claim.condition_name)
        name_font = QFont()
        name_font.setBold(True)
        name_font.setPointSize(10)
        name_lbl.setFont(name_font)
        name_lbl.setStyleSheet("color: #1a1a2e;")
        hdr.addWidget(name_lbl)

        # VASRD code badge
        code_lbl = QLabel(f" DC {self._claim.vasrd_code} ")
        code_lbl.setStyleSheet(
            "background: #e3f0ff; color: #0070c0; border-radius: 4px; "
            "font-size: 11px; font-weight: bold; padding: 1px 4px;"
        )
        hdr.addWidget(code_lbl)

        # Body system badge
        sys_lbl = QLabel(f" {self._claim.body_system} ")
        sys_lbl.setStyleSheet(
            "background: #f0f2f5; color: #555e6e; border-radius: 4px; "
            "font-size: 11px; padding: 1px 4px;"
        )
        hdr.addWidget(sys_lbl)

        # Already claimed badge
        if self._claim.already_claimed:
            claimed_lbl = QLabel(" Already Claimed ")
            claimed_lbl.setStyleSheet(
                "background: #e8f8f0; color: #1a7a4a; border-radius: 4px; "
                "font-size: 11px; font-weight: bold; padding: 1px 6px;"
            )
            hdr.addWidget(claimed_lbl)

        hdr.addStretch()

        # Confidence badge — shows level + numeric score
        score = self._claim.confidence_score
        score_str = f"{score:+.2f}" if score != 0.0 else "0.00"
        conf_lbl = QLabel(f" {self._claim.confidence} ({score_str}) ")
        conf_lbl.setStyleSheet(
            f"background: {self._claim.confidence_bg}; "
            f"color: {self._claim.confidence_color}; "
            "border-radius: 4px; font-size: 11px; font-weight: bold; padding: 1px 6px;"
        )
        hdr.addWidget(conf_lbl)

        # Evidence count
        ev_count_lbl = QLabel(f"{self._claim.evidence_count} ref(s)")
        ev_count_lbl.setStyleSheet("color: #555e6e; font-size: 11px;")
        hdr.addWidget(ev_count_lbl)

        # Expand/collapse button
        self._toggle_btn = QPushButton("▶ View Evidence")
        self._toggle_btn.setObjectName("secondary_btn")
        self._toggle_btn.setFixedHeight(24)
        self._toggle_btn.setFixedWidth(110)
        self._toggle_btn.clicked.connect(self._toggle_evidence)
        hdr.addWidget(self._toggle_btn)

        outer.addLayout(hdr)

        # --- Evidence panel (hidden by default) ---
        self._evidence_frame = QFrame()
        self._evidence_frame.setVisible(False)
        ev_layout = QVBoxLayout(self._evidence_frame)
        ev_layout.setContentsMargins(28, 4, 0, 4)
        ev_layout.setSpacing(8)

        for ev in self._claim.evidence:
            ev_widget = self._make_evidence_item(ev)
            ev_layout.addWidget(ev_widget)

        # Summary line: positive / negation / uncertain counts
        pos   = sum(1 for e in self._claim.evidence if e.positive_diagnosis)
        neg   = sum(1 for e in self._claim.evidence if e.negation_detected or e.family_history)
        uncrt = sum(1 for e in self._claim.evidence if e.uncertainty_flag)
        parts = []
        if pos:
            parts.append(f"✓ {pos} positive")
        if neg:
            parts.append(f"⚠ {neg} negative")
        if uncrt:
            parts.append(f"~ {uncrt} uncertain")
        if parts:
            summary_lbl = QLabel("  " + "  ·  ".join(parts) + f"  (avg score: {score_str})")
            summary_lbl.setStyleSheet(
                "font-size: 11px; color: #666; font-style: italic; padding: 2px 4px;"
            )
            ev_layout.addWidget(summary_lbl)

        outer.addWidget(self._evidence_frame)

    def _make_evidence_item(self, ev) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(0, 2, 0, 2)
        layout.setSpacing(2)

        # Source line + pattern indicator
        from app.config import DOC_TYPES
        doc_type_label = DOC_TYPES.get(ev.doc_type, ev.doc_type)

        # Pattern indicator badge color
        if ev.negation_detected or ev.family_history:
            ind_bg, ind_fg = "#fdf0ef", "#c0392b"
        elif ev.positive_diagnosis:
            ind_bg, ind_fg = "#e8f8f0", "#1a7a4a"
        elif ev.uncertainty_flag:
            ind_bg, ind_fg = "#fff8e1", "#b8610a"
        else:
            ind_bg, ind_fg = "#f0f2f5", "#555e6e"

        src_lbl = QLabel(
            f"<b>{ev.doc_name}</b>  ·  Page {ev.page_number}  "
            f"<span style='color:#555e6e; font-size:11px;'>[{doc_type_label}]</span>"
            f"  <span style='background:{ind_bg}; color:{ind_fg}; "
            f"border-radius:3px; padding:1px 5px; font-size:11px;'>"
            f"{ev.pattern_icon} {ev.pattern_label}</span>"
        )
        src_lbl.setTextFormat(Qt.TextFormat.RichText)
        src_lbl.setStyleSheet("font-size: 12px; color: #1a1a2e;")
        layout.addWidget(src_lbl)

        # Snippet text — muted for negations, highlighted for positives
        if ev.negation_detected or ev.family_history:
            border_color = "#e74c3c"
            snippet_style = (
                "font-size: 11px; opacity: 0.7; "
                f"border-left: 3px solid {border_color}; "
                "padding: 4px 8px; border-radius: 2px;"
            )
        elif ev.positive_diagnosis:
            border_color = "#27ae60"
            snippet_style = (
                "font-size: 11px; "
                f"border-left: 3px solid {border_color}; "
                "padding: 4px 8px; border-radius: 2px;"
            )
        else:
            border_color = "#0070c0"
            snippet_style = (
                "font-size: 11px; "
                f"border-left: 3px solid {border_color}; "
                "padding: 4px 8px; border-radius: 2px;"
            )

        snippet_lbl = QLabel(f"<i>...{ev.snippet}...</i>")
        snippet_lbl.setTextFormat(Qt.TextFormat.RichText)
        snippet_lbl.setWordWrap(True)
        snippet_lbl.setStyleSheet(snippet_style)
        layout.addWidget(snippet_lbl)

        return w

    def _toggle_evidence(self):
        self._evidence_visible = not self._evidence_visible
        self._evidence_frame.setVisible(self._evidence_visible)
        self._toggle_btn.setText(
            "▼ Hide Evidence" if self._evidence_visible else "▶ View Evidence"
        )

    def is_checked(self) -> bool:
        return self._checkbox.isChecked()

    def get_claim(self):
        return self._claim


# ---------------------------------------------------------------------------
# Main dialog
# ---------------------------------------------------------------------------

class ScanResultsDialog(QDialog):
    """
    Shows context-aware analysis results and lets the user create draft claims.

    Emits `claims_created` when draft claims have been created so the
    parent can refresh the claims panel.
    """
    claims_created = pyqtSignal()

    def __init__(self, veteran_id: int, parent=None):
        super().__init__(parent)
        self._veteran_id = veteran_id
        self._cards: list[_ConditionCard] = []
        self._all_claims: list = []
        self._active_filter = "all"
        self.setWindowTitle("Medical Record Analysis")
        self.setMinimumSize(900, 700)
        self.setModal(True)
        self._build_ui()
        self._start_scan()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(10)

        # Title
        title = QLabel("Medical Record Analysis")
        title.setObjectName("section_header")
        layout.addWidget(title)

        self._subtitle = QLabel("Scanning indexed documents for potential disability conditions...")
        self._subtitle.setStyleSheet("color: #555e6e; font-size: 13px;")
        layout.addWidget(self._subtitle)

        # Progress area (visible during scan)
        self._progress_bar = QProgressBar()
        self._progress_bar.setTextVisible(True)
        layout.addWidget(self._progress_bar)

        self._progress_label = QLabel("")
        self._progress_label.setStyleSheet("color: #555e6e; font-size: 12px;")
        layout.addWidget(self._progress_label)

        # Filter bar + select-all (hidden until results load)
        self._filter_bar = QWidget()
        filter_layout = QHBoxLayout(self._filter_bar)
        filter_layout.setContentsMargins(0, 0, 0, 0)
        filter_layout.setSpacing(6)

        self._btn_all      = self._filter_btn("All",           "all")
        self._btn_high     = self._filter_btn("High",          "High",     "#e8f8f0", "#1a7a4a")
        self._btn_med      = self._filter_btn("Medium",        "Medium",   "#fff3e0", "#b8610a")
        self._btn_low      = self._filter_btn("Low",           "Low",      "#f0f2f5", "#555e6e")
        self._btn_vlow     = self._filter_btn("Very Low",      "Very Low", "#f5f5fc", "#7a7a99")
        self._btn_excluded = self._filter_btn("Excluded",      "Negative", "#fdf0ef", "#c0392b")
        self._btn_unclaimed = self._filter_btn("Not Yet Claimed", "unclaimed")

        for b in [self._btn_all, self._btn_high, self._btn_med,
                  self._btn_low, self._btn_vlow, self._btn_excluded,
                  self._btn_unclaimed]:
            filter_layout.addWidget(b)

        filter_layout.addStretch()

        self._select_all_cb = QCheckBox("Select All")
        self._select_all_cb.stateChanged.connect(self._on_select_all)
        filter_layout.addWidget(self._select_all_cb)

        self._filter_bar.setVisible(False)
        layout.addWidget(self._filter_bar)

        # Disclaimer banner
        self._disclaimer = QFrame()
        self._disclaimer.setStyleSheet(
            "QFrame { background:#fff8e1; border:1px solid #ffc107; border-radius:6px; padding:2px; }"
        )
        disc_layout = QHBoxLayout(self._disclaimer)
        disc_layout.setContentsMargins(10, 6, 10, 6)
        disc_icon = QLabel("ℹ")
        disc_icon.setStyleSheet("font-size:16px; color:#b8610a;")
        disc_layout.addWidget(disc_icon)
        disc_text = QLabel(
            "Conditions scored using context-aware analysis: ✓ Positive Diagnosis, "
            "⚠ Negation/Family History (excluded), ~ Uncertain.  "
            "Review each item and verify evidence before creating draft claims."
        )
        disc_text.setWordWrap(True)
        disc_text.setStyleSheet("color:#5d4037; font-size:12px; background:transparent;")
        disc_layout.addWidget(disc_text)
        self._disclaimer.setVisible(False)
        layout.addWidget(self._disclaimer)

        # Scroll area for condition cards
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll_container = QWidget()
        self._scroll_layout = QVBoxLayout(self._scroll_container)
        self._scroll_layout.setContentsMargins(2, 4, 2, 4)
        self._scroll_layout.setSpacing(4)
        self._scroll_layout.addStretch()
        self._scroll.setWidget(self._scroll_container)
        layout.addWidget(self._scroll)

        # Bottom action row
        action_row = QHBoxLayout()
        self._selected_count_lbl = QLabel("")
        self._selected_count_lbl.setStyleSheet("color: #555e6e; font-size: 12px;")
        action_row.addWidget(self._selected_count_lbl)
        action_row.addStretch()

        self._btn_create = QPushButton("Create Draft Claims")
        self._btn_create.setFixedWidth(180)
        self._btn_create.setEnabled(False)
        self._btn_create.clicked.connect(self._on_create_claims)
        action_row.addWidget(self._btn_create)

        self._btn_close = QPushButton("Close")
        self._btn_close.setObjectName("secondary_btn")
        self._btn_close.setFixedWidth(90)
        self._btn_close.clicked.connect(self.reject)
        action_row.addWidget(self._btn_close)

        layout.addLayout(action_row)

    def _filter_btn(self, label: str, key: str,
                    bg: str = "#f0f2f5", fg: str = "#555e6e") -> QPushButton:
        btn = QPushButton(label)
        btn.setCheckable(True)
        btn.setChecked(key == "all")
        btn.setFixedHeight(26)
        btn.setStyleSheet(
            f"QPushButton {{ background:{bg}; color:{fg}; border:1px solid #dde2e8; "
            f"border-radius:12px; padding:0 10px; font-size:11px; font-weight:bold; }}"
            f"QPushButton:checked {{ background:{fg}; color:white; border-color:{fg}; }}"
        )
        btn.clicked.connect(lambda checked, k=key: self._apply_filter(k))
        return btn

    # ------------------------------------------------------------------
    # Scan
    # ------------------------------------------------------------------

    def _start_scan(self):
        import app.db.repositories.claim_repo as claim_repo
        claims = claim_repo.get_all(self._veteran_id)
        existing = {c.condition_name for c in claims}

        worker = _ScanWorker(self._veteran_id, existing)
        worker.signals.progress.connect(self._on_scan_progress)
        worker.signals.finished.connect(self._on_scan_finished)
        worker.signals.error.connect(self._on_scan_error)
        get_thread_pool().start(worker)

    def _on_scan_progress(self, current: int, total: int, message: str):
        self._progress_bar.setMaximum(max(total, 1))
        self._progress_bar.setValue(current)
        self._progress_label.setText(message)

    def _on_scan_finished(self, results: list, doc_count: int, page_count: int):
        self._progress_bar.setVisible(False)
        self._progress_label.setVisible(False)
        self._all_claims = results

        if not results:
            self._subtitle.setText(
                f"Scanned {doc_count} document(s) ({page_count:,} pages). "
                "No potential conditions were identified. "
                "This may mean the records don't contain diagnostic text, "
                "or OCR may need to be improved."
            )
            return

        # Counts per level
        high     = sum(1 for c in results if c.confidence == "High")
        med      = sum(1 for c in results if c.confidence == "Medium")
        low      = sum(1 for c in results if c.confidence == "Low")
        vlow     = sum(1 for c in results if c.confidence == "Very Low")
        negative = sum(1 for c in results if c.confidence == "Negative")
        unclaimed = sum(1 for c in results if not c.already_claimed
                        and c.confidence != "Negative")
        visible  = len(results) - negative

        self._btn_all.setText(f"All ({visible})")
        self._btn_high.setText(f"High ({high})")
        self._btn_med.setText(f"Medium ({med})")
        self._btn_low.setText(f"Low ({low})")
        self._btn_vlow.setText(f"Very Low ({vlow})")
        self._btn_excluded.setText(f"Excluded ({negative})")
        self._btn_unclaimed.setText(f"Not Yet Claimed ({unclaimed})")

        self._subtitle.setText(
            f"Scanned {doc_count} document(s)  ·  {page_count:,} pages  ·  "
            f"{visible} potential condition(s) identified"
            + (f"  ·  {negative} excluded (negation-only)" if negative else "")
            + "  —  Select conditions and click 'Create Draft Claims'."
        )

        self._filter_bar.setVisible(True)
        self._disclaimer.setVisible(True)
        self._apply_filter("all")

    def _on_scan_error(self, error: str):
        self._progress_bar.setVisible(False)
        self._progress_label.setVisible(False)
        self._subtitle.setText("Scan failed — see error below.")
        QMessageBox.critical(
            self, "Scan Error",
            f"An error occurred while scanning your records:\n\n{error[:600]}"
        )

    # ------------------------------------------------------------------
    # Filter
    # ------------------------------------------------------------------

    def _apply_filter(self, key: str):
        self._active_filter = key

        for btn, bkey in [
            (self._btn_all,      "all"),
            (self._btn_high,     "High"),
            (self._btn_med,      "Medium"),
            (self._btn_low,      "Low"),
            (self._btn_vlow,     "Very Low"),
            (self._btn_excluded, "Negative"),
            (self._btn_unclaimed, "unclaimed"),
        ]:
            btn.setChecked(bkey == key)

        if key == "all":
            # "All" excludes Negative-scored claims (shown in Excluded tab)
            visible = [c for c in self._all_claims if c.confidence != "Negative"]
        elif key == "unclaimed":
            visible = [c for c in self._all_claims
                       if not c.already_claimed and c.confidence != "Negative"]
        elif key == "Negative":
            visible = [c for c in self._all_claims if c.confidence == "Negative"]
        else:
            visible = [c for c in self._all_claims if c.confidence == key]

        self._rebuild_cards(visible)

    def _rebuild_cards(self, claims: list):
        for card in self._cards:
            self._scroll_layout.removeWidget(card)
            card.deleteLater()
        self._cards.clear()

        item = self._scroll_layout.takeAt(self._scroll_layout.count() - 1)
        if item:
            del item

        for claim in claims:
            card = _ConditionCard(claim)
            self._cards.append(card)
            self._scroll_layout.addWidget(card)

        self._scroll_layout.addStretch()
        self._update_create_button()

        for card in self._cards:
            card._checkbox.stateChanged.connect(self._update_create_button)

    def _on_select_all(self, state: int):
        checked = state == Qt.CheckState.Checked.value
        for card in self._cards:
            if not card._claim.already_claimed and card._claim.confidence != "Negative":
                card._checkbox.blockSignals(True)
                card._checkbox.setChecked(checked)
                card._checkbox.blockSignals(False)
        self._update_create_button()

    def _update_create_button(self):
        n = sum(1 for c in self._cards if c.is_checked())
        if n > 0:
            self._btn_create.setText(f"Create {n} Draft Claim(s)")
            self._btn_create.setEnabled(True)
            self._selected_count_lbl.setText(f"{n} condition(s) selected")
        else:
            self._btn_create.setText("Create Draft Claims")
            self._btn_create.setEnabled(False)
            self._selected_count_lbl.setText("")

    # ------------------------------------------------------------------
    # Create draft claims
    # ------------------------------------------------------------------

    def _on_create_claims(self):
        selected = [c.get_claim() for c in self._cards if c.is_checked()]
        if not selected:
            return

        import json
        from collections import defaultdict
        import app.db.repositories.claim_repo as claim_repo
        import app.db.connection as db_conn
        from app.core.claim import Claim

        created = 0
        skipped = 0
        for potential in selected:
            if potential.already_claimed or potential.confidence == "Negative":
                skipped += 1
                continue

            # Build evidence summary for the claim notes field
            evidence_lines = ["--- Auto-detected evidence references ---"]
            for i, ev in enumerate(potential.evidence, 1):
                indicator = f"[{ev.pattern_icon} {ev.pattern_label}]"
                evidence_lines.append(
                    f"{i}. {ev.doc_name}  (Page {ev.page_number})  {indicator}\n"
                    f"   Keyword matched: '{ev.matched_keyword}'\n"
                    f"   Excerpt: ...{ev.snippet[:200]}..."
                )
            score_str = f"{potential.confidence_score:+.2f}"
            evidence_lines.append(
                f"\n--- Confidence: {potential.confidence} (score {score_str}) ---"
            )
            notes = "\n".join(evidence_lines)

            claim = Claim(
                id=None,
                veteran_id=self._veteran_id,
                condition_name=potential.condition_name,
                vasrd_code=potential.vasrd_code,
                body_system=potential.body_system,
                claim_type="direct",
                status="building",
                notes=notes,
            )
            claim.compute_risks()
            try:
                new_claim_id = claim_repo.create(claim)

                # Link each evidence document to this claim
                doc_pages: dict[int, list] = defaultdict(list)
                for ev in potential.evidence:
                    doc_pages[ev.document_id].append({
                        "page_number":  ev.page_number,
                        "page_id":      ev.page_id,
                        "keyword":      ev.matched_keyword,
                        "snippet":      ev.snippet[:400],
                        "pattern_label": ev.pattern_label,
                        "positive":     ev.positive_diagnosis,
                        "negated":      ev.negation_detected or ev.family_history,
                    })

                conn = db_conn.get_connection()
                with conn:
                    for doc_id, pages in doc_pages.items():
                        notes_json = json.dumps({
                            "auto_detected": True,
                            "condition":     potential.condition_name,
                            "confidence":    potential.confidence,
                            "score":         round(potential.confidence_score, 3),
                            "pages":         pages,
                        })
                        conn.execute(
                            """INSERT OR REPLACE INTO claim_documents
                               (claim_id, document_id, role, notes)
                               VALUES (?, ?, 'supporting', ?)""",
                            (new_claim_id, doc_id, notes_json),
                        )

                created += 1
            except Exception as exc:
                log.warning("Failed to create draft claim for %s: %s",
                            potential.condition_name, exc)

        if created:
            QMessageBox.information(
                self, "Draft Claims Created",
                f"{created} draft claim(s) created successfully.\n\n"
                "Go to the Claims tab to review each one, verify the evidence, "
                "and complete the Caluza Triangle (Diagnosis, In-Service Event, and Nexus) "
                "before submitting to the VA."
            )
            self.claims_created.emit()
            self.accept()
        else:
            QMessageBox.warning(self, "Nothing Created",
                                "No new claims were created. "
                                "All selected conditions may already be claimed.")
