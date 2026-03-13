"""
Evidence Documents Panel — displays and manages claim-linked documents.

Shows all documents linked to a claim via the claim_documents join table.
Each card includes a role selector (Diagnosis / In-Service / Nexus / etc.)
and a Remove button. Page-level evidence snippets are shown inline.

Public API:
    load_evidence(claim_id: int)  — query DB and render all linked documents
    clear()                       — reset to empty state
"""
from __future__ import annotations
import json
import html

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QComboBox,
)

from app.db.connection import get_connection


class EvidencePanel(QWidget):
    """Shows documents linked to a claim with role selectors and remove buttons."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self):
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(12, 10, 12, 10)
        self._layout.setSpacing(6)

        self._empty_lbl = QLabel(
            "  No evidence documents linked yet.\n"
            "  Use 'Analyze Records' in the Documents tab to auto-detect evidence,\n"
            "  or assign documents manually via the role dropdowns above."
        )
        self._empty_lbl.setStyleSheet("color: #888; font-size: 12px; padding: 6px;")
        self._layout.addWidget(self._empty_lbl)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load_evidence(self, claim_id: int):
        """Load claim_documents for this claim and render a card per document."""
        self.clear()

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

        self._empty_lbl.setVisible(False)

        for row in rows:
            doc_id = row["document_id"]
            row_role = row["role"] or "supporting"
            filename = row["filename"] or "Unknown file"
            doc_type = row["doc_type"] or "Document"
            notes_raw = row["notes"] or "{}"

            try:
                notes = json.loads(notes_raw)
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

            # Header: filename + doc-type badge
            header_row = QHBoxLayout()
            fname_lbl = QLabel(f"<b>{html.escape(filename)}</b>")
            fname_lbl.setStyleSheet("font-size: 13px;")
            header_row.addWidget(fname_lbl)

            type_badge = QLabel(f"  {html.escape(doc_type)}  ")
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

            # Role selector + Remove button
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
            for i in range(role_combo.count()):
                if role_combo.itemData(i) == row_role:
                    role_combo.setCurrentIndex(i)
                    break
            role_combo.setFixedWidth(200)
            role_combo.setStyleSheet("font-size: 12px;")

            _cid = claim_id
            _did = doc_id
            _orig_role = row_role

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

            # Page evidence snippets (up to 3)
            if pages:
                for page_info in pages[:3]:
                    pg_num = page_info.get("page_number", "?")
                    keyword = page_info.get("keyword", "")
                    snippet = page_info.get("snippet", "")[:300]
                    if snippet:
                        snippet_text = f"<i>Page {html.escape(str(pg_num))}</i>"
                        if keyword:
                            snippet_text += f" &nbsp;·&nbsp; keyword: <b>{html.escape(keyword)}</b>"
                        snippet_text += (
                            f"<br><span style='color:#444;font-size:11px;'>"
                            f"{html.escape(snippet)}</span>"
                        )
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

            self._layout.addWidget(card)

    def clear(self):
        """Remove all evidence cards and show the empty-state label."""
        while self._layout.count():
            item = self._layout.takeAt(0)
            widget = item.widget()
            if widget and widget is not self._empty_lbl:
                widget.deleteLater()
        self._empty_lbl.setVisible(True)
        self._layout.addWidget(self._empty_lbl)
