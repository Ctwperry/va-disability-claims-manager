"""
Export panel: configure and generate the VA claim package.
"""
import os
from pathlib import Path
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QCheckBox, QFileDialog, QProgressBar, QTextEdit,
    QMessageBox, QScrollArea, QGroupBox, QLineEdit
)
from PyQt6.QtCore import Qt, QRunnable, QObject, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QFont

from app.config import EXPORTS_DIR
from app.db.schema import get_setting, set_setting
import app.db.repositories.veteran_repo as veteran_repo
import app.db.repositories.claim_repo as claim_repo
import app.db.repositories.document_repo as doc_repo
from app.ui.workers import get_thread_pool


class _ExportSignals(QObject):
    progress = pyqtSignal(int, int, str)
    finished = pyqtSignal(str)   # path to output dir
    error = pyqtSignal(str)


class _ExportWorker(QRunnable):
    def __init__(self, veteran_id: int, output_dir: Path):
        super().__init__()
        self.veteran_id = veteran_id
        self.output_dir = output_dir
        self.signals = _ExportSignals()
        self.setAutoDelete(True)

    @pyqtSlot()
    def run(self):
        try:
            from app.export.package_builder import build_package
            pkg_path = build_package(
                self.veteran_id,
                self.output_dir,
                progress_cb=lambda c, t, m: self.signals.progress.emit(c, t, m),
            )
            self.signals.finished.emit(str(pkg_path))
        except Exception as exc:
            import traceback
            self.signals.error.emit(traceback.format_exc())


class ExportPanel(QWidget):
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
        layout.setSpacing(14)

        title = QLabel("Export Claim Package")
        title.setObjectName("section_header")
        layout.addWidget(title)

        desc = QLabel(
            "Generate a complete, organized folder containing all claim documents, "
            "Caluza Triangle summaries, and a required forms checklist — "
            "ready to submit to the VA Regional Office."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #555e6e; font-size: 13px;")
        layout.addWidget(desc)

        # Output directory
        layout.addWidget(self._section_lbl("Output Directory"))
        dir_card = self._card()
        dir_layout = QHBoxLayout(dir_card)
        dir_layout.setContentsMargins(14, 10, 14, 10)

        self._output_dir = QLineEdit()
        default_dir = get_setting("default_export_dir", "") or str(EXPORTS_DIR)
        self._output_dir.setText(default_dir)
        dir_layout.addWidget(self._output_dir)

        browse_btn = QPushButton("Browse...")
        browse_btn.setObjectName("secondary_btn")
        browse_btn.setFixedWidth(90)
        browse_btn.clicked.connect(self._browse_dir)
        dir_layout.addWidget(browse_btn)
        layout.addWidget(dir_card)

        # Package contents preview
        layout.addWidget(self._section_lbl("Package Contents Preview"))
        self._preview = QTextEdit()
        self._preview.setReadOnly(True)
        self._preview.setStyleSheet(
            "QTextEdit { border-radius: 6px; font-family: Consolas, monospace; "
            "font-size: 12px; padding: 10px; }"
        )
        self._preview.setMinimumHeight(240)
        layout.addWidget(self._preview)

        # Progress
        self._progress_bar = QProgressBar()
        self._progress_bar.setVisible(False)
        layout.addWidget(self._progress_bar)

        self._progress_label = QLabel("")
        self._progress_label.setStyleSheet("color: #555e6e; font-size: 12px;")
        layout.addWidget(self._progress_label)

        # Generate button
        gen_row = QHBoxLayout()
        gen_row.addStretch()

        self._btn_refresh_preview = QPushButton("Refresh Preview")
        self._btn_refresh_preview.setObjectName("secondary_btn")
        self._btn_refresh_preview.setFixedWidth(150)
        self._btn_refresh_preview.clicked.connect(self._update_preview)
        gen_row.addWidget(self._btn_refresh_preview)

        self._btn_generate = QPushButton("Generate Package")
        self._btn_generate.setFixedWidth(160)
        self._btn_generate.clicked.connect(self._on_generate)
        gen_row.addWidget(self._btn_generate)
        layout.addLayout(gen_row)

        layout.addStretch()
        scroll.setWidget(container)
        outer.addWidget(scroll)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load_veteran(self, veteran_id: int | None):
        self._veteran_id = veteran_id
        self._update_preview()

    # ------------------------------------------------------------------

    def _browse_dir(self):
        path = QFileDialog.getExistingDirectory(
            self, "Select Output Directory", self._output_dir.text()
        )
        if path:
            self._output_dir.setText(path)
            set_setting("default_export_dir", path)

    def _update_preview(self):
        if not self._veteran_id:
            self._preview.setPlainText("No veteran selected.")
            return

        veteran = veteran_repo.get_by_id(self._veteran_id)
        claims = claim_repo.get_all(self._veteran_id)
        docs = doc_repo.get_all(self._veteran_id)

        from app.config import DOC_TYPES
        from collections import Counter

        lines = [
            f"Package for: {veteran.full_name}",
            f"Branch: {veteran.branch}  |  Era: {veteran.era}",
            "",
            "Folder Structure:",
            "  📁 [VeteranName]_[Timestamp]/",
            "     📄 00_Cover_Sheet.txt",
        ]

        dd214_count = sum(1 for d in docs if d.doc_type == "DD214")
        str_count = sum(1 for d in docs if d.doc_type == "STR")
        buddy_count = sum(1 for d in docs if d.doc_type in ("BuddyStatement", "SupportStatement"))
        other_count = sum(1 for d in docs if d.doc_type in ("PrivateMedical", "VAMedical", "Other"))

        if dd214_count:
            lines.append(f"     📁 01_DD214/  ({dd214_count} file(s))")
        if str_count:
            lines.append(f"     📁 02_ServiceTreatmentRecords/  ({str_count} file(s))")

        lines.append(f"     📁 03_Claims/  ({len(claims)} claim(s))")
        for claim in claims:
            triangle = f"{'✓' if claim.has_diagnosis else '✗'}Dx {'✓' if claim.has_inservice_event else '✗'}Ev {'✓' if claim.has_nexus else '✗'}Nx"
            risks = f"  ⚠ {claim.risk_count} risk(s)" if claim.risk_count else ""
            lines.append(f"        📁 {claim.condition_name} {claim.vasrd_code or ''}")
            lines.append(f"           [{triangle}]{risks}")
            lines.append(f"           📄 Claim_Summary.txt")

        lines.append("     📁 04_Forms/")
        lines.append("        📄 Required_Forms_Checklist.txt")
        if buddy_count:
            lines.append(f"     📁 05_Buddy_Statements/  ({buddy_count} file(s))")
        if other_count:
            lines.append(f"     📁 06_Other_Medical_Records/  ({other_count} file(s))")

        lines += [
            "",
            f"Total documents to copy: {len(docs)}",
            f"Total indexed pages: {sum(d.page_count for d in docs):,}",
        ]

        incomplete = [c for c in claims if not c.triangle_complete]
        if incomplete:
            lines += ["", f"⚠  {len(incomplete)} claim(s) have incomplete Caluza Triangle:"]
            for c in incomplete:
                missing = []
                if not c.has_diagnosis:
                    missing.append("Diagnosis")
                if not c.has_inservice_event:
                    missing.append("In-Service Event")
                if not c.has_nexus:
                    missing.append("Nexus")
                lines.append(f"   • {c.condition_name}: missing {', '.join(missing)}")

        self._preview.setPlainText("\n".join(lines))

    def _on_generate(self):
        if not self._veteran_id:
            QMessageBox.information(self, "No Veteran", "Please select a veteran first.")
            return

        output_dir = Path(self._output_dir.text().strip())
        if not output_dir.exists():
            try:
                output_dir.mkdir(parents=True)
            except Exception as exc:
                QMessageBox.critical(self, "Error", f"Cannot create output directory:\n{exc}")
                return

        self._btn_generate.setEnabled(False)
        self._progress_bar.setVisible(True)
        self._progress_bar.setValue(0)

        worker = _ExportWorker(self._veteran_id, output_dir)
        worker.signals.progress.connect(self._on_progress)
        worker.signals.finished.connect(self._on_done)
        worker.signals.error.connect(self._on_error)
        get_thread_pool().start(worker)

    def _on_progress(self, current: int, total: int, message: str):
        self._progress_bar.setMaximum(max(total, 1))
        self._progress_bar.setValue(current)
        self._progress_label.setText(message)

    def _on_done(self, pkg_path: str):
        self._btn_generate.setEnabled(True)
        self._progress_bar.setVisible(False)
        self._progress_label.setText(f"Package created at: {pkg_path}")

        reply = QMessageBox.information(
            self, "Package Created",
            f"Claim package successfully created at:\n\n{pkg_path}\n\n"
            "Open the folder now?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            os.startfile(pkg_path)

    def _on_error(self, error: str):
        self._btn_generate.setEnabled(True)
        self._progress_bar.setVisible(False)
        QMessageBox.critical(self, "Export Error", f"Package generation failed:\n\n{error[:500]}")

    @staticmethod
    def _section_lbl(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setObjectName("subsection_header")
        return lbl

    @staticmethod
    def _card() -> QFrame:
        card = QFrame()
        card.setObjectName("card")
        return card
