"""
Document library panel: drag-and-drop ingestion + sortable document table.
"""
import os
from pathlib import Path
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QFileDialog,
    QProgressBar, QComboBox, QFrame, QAbstractItemView,
    QMessageBox, QSizePolicy, QMenu
)
from PyQt6.QtCore import Qt, pyqtSignal, QUrl, QTimer
from PyQt6.QtGui import QDragEnterEvent, QDropEvent, QColor, QBrush

from app.config import DOC_TYPES
from app.core.document import Document
import app.db.repositories.document_repo as doc_repo
from app.ui.workers import IngestionWorker, get_thread_pool


class DocumentPanel(QWidget):
    documents_updated = pyqtSignal()   # emitted when new docs finish ingesting
    analyze_requested = pyqtSignal()   # emitted when user wants to scan records

    def __init__(self, parent=None):
        super().__init__(parent)
        self._veteran_id: int | None = None
        self._setAcceptDrops(True)
        self._build_ui()

    def _setAcceptDrops(self, val):
        self.setAcceptDrops(val)

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)

        # Header
        hdr = QHBoxLayout()
        title = QLabel("Documents")
        title.setObjectName("section_header")
        hdr.addWidget(title)
        hdr.addStretch()

        self._filter_combo = QComboBox()
        self._filter_combo.addItem("All Types", "")
        for key, label in DOC_TYPES.items():
            self._filter_combo.addItem(label, key)
        self._filter_combo.setFixedWidth(220)
        self._filter_combo.currentIndexChanged.connect(self._refresh_table)
        hdr.addWidget(QLabel("Filter:"))
        hdr.addWidget(self._filter_combo)

        self._btn_add = QPushButton("+ Add Files")
        self._btn_add.setFixedWidth(110)
        self._btn_add.clicked.connect(self._on_add_files)
        hdr.addWidget(self._btn_add)

        self._btn_analyze = QPushButton("🔍 Analyze Records")
        self._btn_analyze.setFixedWidth(150)
        self._btn_analyze.setToolTip(
            "Scan all indexed documents for potential VA disability conditions "
            "and create draft claims for review."
        )
        self._btn_analyze.setEnabled(False)
        self._btn_analyze.clicked.connect(self._on_analyze)
        hdr.addWidget(self._btn_analyze)

        layout.addLayout(hdr)

        # Drop zone
        self._drop_zone = _DropZone()
        self._drop_zone.files_dropped.connect(self._on_files_dropped)
        layout.addWidget(self._drop_zone)

        # Progress bar
        self._progress_bar = QProgressBar()
        self._progress_bar.setVisible(False)
        self._progress_bar.setTextVisible(True)
        layout.addWidget(self._progress_bar)

        self._progress_label = QLabel("")
        self._progress_label.setVisible(False)
        self._progress_label.setStyleSheet("color: #555e6e; font-size: 12px;")
        layout.addWidget(self._progress_label)

        # Document table
        self._table = QTableWidget()
        self._table.setColumnCount(7)
        self._table.setHorizontalHeaderLabels([
            "Filename", "Type", "Date", "Pages", "Size", "OCR", "Status"
        ])
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setAlternatingRowColors(True)
        self._table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._table.customContextMenuRequested.connect(self._context_menu)
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)
        self._table.verticalHeader().setVisible(False)
        self._table.setShowGrid(False)
        layout.addWidget(self._table)

        # Stats footer
        self._stats_label = QLabel("No documents")
        self._stats_label.setStyleSheet("color: #555e6e; font-size: 12px;")
        layout.addWidget(self._stats_label)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load_veteran(self, veteran_id: int | None):
        self._veteran_id = veteran_id
        self._refresh_table()
        self._update_analyze_button()

    # ------------------------------------------------------------------
    # Events
    # ------------------------------------------------------------------

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event: QDropEvent):
        urls = event.mimeData().urls()
        paths = [u.toLocalFile() for u in urls if u.toLocalFile()]
        if paths:
            self._on_files_dropped(paths)

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _on_add_files(self):
        if not self._veteran_id:
            QMessageBox.information(self, "No Veteran", "Please select a veteran first.")
            return
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Select Medical Documents",
            os.path.expanduser("~"),
            "Documents (*.pdf *.docx *.doc *.jpg *.jpeg *.png *.tiff *.tif *.bmp);;All Files (*)"
        )
        if paths:
            self._on_files_dropped(paths)

    def _on_files_dropped(self, paths: list[str]):
        if not self._veteran_id:
            QMessageBox.information(self, "No Veteran", "Please select a veteran first.")
            return
        if not paths:
            return

        self._progress_bar.setVisible(True)
        self._progress_label.setVisible(True)
        self._progress_bar.setValue(0)
        self._progress_bar.setMaximum(len(paths))
        self._btn_add.setEnabled(False)

        worker = IngestionWorker(paths, self._veteran_id)
        worker.signals.progress.connect(self._on_progress)
        worker.signals.result.connect(self._on_ingestion_done)
        worker.signals.error.connect(self._on_ingestion_error)
        get_thread_pool().start(worker)

    def _on_progress(self, current: int, total: int, message: str):
        self._progress_bar.setMaximum(max(total, 1))
        self._progress_bar.setValue(current)
        self._progress_label.setText(message)

    def _on_ingestion_done(self, results: list):
        self._progress_bar.setVisible(False)
        self._progress_label.setVisible(False)
        self._btn_add.setEnabled(True)

        success = sum(1 for r in results if r["status"] == "success")
        duplicate = sum(1 for r in results if r["status"] == "duplicate")
        errors = sum(1 for r in results if r["status"] == "error")

        msg_parts = []
        if success:
            msg_parts.append(f"{success} document(s) imported")
        if duplicate:
            msg_parts.append(f"{duplicate} duplicate(s) skipped")
        if errors:
            msg_parts.append(f"{errors} error(s)")
            error_msgs = [f"  • {r['filename']}: {r['message']}"
                         for r in results if r["status"] == "error"]
            QMessageBox.warning(
                self, "Import Errors",
                "Some files could not be imported:\n\n" + "\n".join(error_msgs)
            )

        self._refresh_table()
        self._update_analyze_button()
        self.documents_updated.emit()

        if msg_parts:
            self._stats_label.setText(" | ".join(msg_parts))
            QTimer.singleShot(5000, self._update_stats_label)

        # Offer to run the condition scan when new documents are added
        if success >= 1:
            reply = QMessageBox.question(
                self,
                "Analyze Records for Conditions?",
                f"{success} document(s) successfully imported.\n\n"
                "Would you like to automatically scan these records for potential "
                "VA disability conditions you could claim?\n\n"
                "The scan will review all indexed documents and show you a list of "
                "conditions found, with the exact page and document where each was "
                "mentioned, so you can decide which claims to file.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes,
            )
            if reply == QMessageBox.StandardButton.Yes:
                self._on_analyze()

    def _on_ingestion_error(self, error: str):
        self._progress_bar.setVisible(False)
        self._progress_label.setVisible(False)
        self._btn_add.setEnabled(True)
        # Show the tail of the traceback — that's where the actual exception type/message is
        display = error[-1200:] if len(error) > 1200 else error
        QMessageBox.critical(self, "Ingestion Error",
                             f"An unexpected error occurred:\n\n{display}")

    def _on_analyze(self):
        if not self._veteran_id:
            QMessageBox.information(self, "No Veteran", "Please select a veteran first.")
            return
        from app.ui.dialogs.scan_results_dialog import ScanResultsDialog
        dlg = ScanResultsDialog(self._veteran_id, parent=self)
        dlg.claims_created.connect(self.documents_updated)  # reuse signal to refresh dashboard
        dlg.exec()

    def _update_analyze_button(self):
        if not self._veteran_id:
            self._btn_analyze.setEnabled(False)
            return
        count = doc_repo.count(self._veteran_id)
        self._btn_analyze.setEnabled(count > 0)

    def _context_menu(self, pos):
        item = self._table.itemAt(pos)
        if item is None:
            return
        row = self._table.currentRow()
        doc_id = self._table.item(row, 0).data(Qt.ItemDataRole.UserRole)
        if doc_id is None:
            return

        menu = QMenu(self)
        action_open = menu.addAction("Open File Location")
        menu.addSeparator()
        action_delete = menu.addAction("Remove Document")

        action = menu.exec(self._table.mapToGlobal(pos))

        if action == action_open:
            self._open_file_location(doc_id)

        elif action == action_delete:
            doc = doc_repo.get_by_id(doc_id)
            name = doc.filename if doc else "this document"
            reply = QMessageBox.question(
                self, "Remove Document",
                f"Remove '{name}' from the database?\n"
                "(The original file will not be deleted.)",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.Yes:
                doc_repo.delete(doc_id)
                self._refresh_table()
                self.documents_updated.emit()

    def _open_file_location(self, doc_id: int):
        from app.core.path_guard import safe_file_path
        doc = doc_repo.get_by_id(doc_id)
        if not doc:
            QMessageBox.warning(self, "Not Found", "The file could not be located.")
            return
        # Validate the file before opening its parent — rejects symlinks and
        # missing paths before they reach the OS file browser.
        safe_file = safe_file_path(Path(doc.filepath))
        if safe_file is None:
            QMessageBox.warning(self, "Not Found", "The file could not be located.")
            return
        os.startfile(str(safe_file.parent))

    # ------------------------------------------------------------------
    # Table refresh
    # ------------------------------------------------------------------

    def _refresh_table(self):
        if not self._veteran_id:
            self._table.setRowCount(0)
            self._stats_label.setText("No veteran selected")
            return

        filter_type = self._filter_combo.currentData() or None
        docs = doc_repo.get_all(self._veteran_id, doc_type=filter_type)

        self._table.setRowCount(len(docs))
        for row, doc in enumerate(docs):
            # Filename (stores doc_id as UserRole)
            name_item = QTableWidgetItem(doc.filename)
            name_item.setData(Qt.ItemDataRole.UserRole, doc.id)
            name_item.setToolTip(doc.filepath)
            self._table.setItem(row, 0, name_item)

            # Type
            type_label = DOC_TYPES.get(doc.doc_type, doc.doc_type)
            self._table.setItem(row, 1, QTableWidgetItem(type_label))

            # Date
            self._table.setItem(row, 2, QTableWidgetItem(doc.doc_date or ""))

            # Pages
            pg_item = QTableWidgetItem(str(doc.page_count))
            pg_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._table.setItem(row, 3, pg_item)

            # Size
            self._table.setItem(row, 4, QTableWidgetItem(doc.size_display))

            # OCR
            ocr_item = QTableWidgetItem("Yes" if doc.ocr_performed else "No")
            ocr_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._table.setItem(row, 5, ocr_item)

            # Status
            status_item = QTableWidgetItem(doc.ingestion_status.title())
            if doc.ingestion_status == "complete":
                status_item.setForeground(QBrush(QColor("#1a7a4a")))
            elif doc.ingestion_status == "error":
                status_item.setForeground(QBrush(QColor("#c0392b")))
            elif doc.ingestion_status == "processing":
                status_item.setForeground(QBrush(QColor("#b8610a")))
            self._table.setItem(row, 6, status_item)

        self._update_stats_label()

    def _update_stats_label(self):
        if not self._veteran_id:
            return
        count = doc_repo.count(self._veteran_id)
        all_docs = doc_repo.get_all(self._veteran_id)
        total_pages = sum(d.page_count for d in all_docs)
        self._stats_label.setText(
            f"{count} document(s) indexed  |  {total_pages:,} total pages searchable"
        )


class _DropZone(QFrame):
    files_dropped = pyqtSignal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setFixedHeight(80)
        self.setObjectName("card")
        self.setStyleSheet(
            "QFrame#card { border: 2px dashed #0070c0; background-color: #f0f6ff; border-radius: 8px; }"
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        lbl = QLabel("Drag & drop PDF, Word, or image files here  —  or click '+ Add Files'")
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setStyleSheet("color: #0070c0; font-size: 13px; background: transparent;")
        layout.addWidget(lbl)

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            self.setStyleSheet(
                "QFrame { border: 2px solid #0070c0; background-color: #e3f0ff; border-radius: 8px; }"
            )
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragLeaveEvent(self, event):
        self.setStyleSheet(
            "QFrame#card { border: 2px dashed #0070c0; background-color: #f0f6ff; border-radius: 8px; }"
        )

    def dropEvent(self, event: QDropEvent):
        self.setStyleSheet(
            "QFrame#card { border: 2px dashed #0070c0; background-color: #f0f6ff; border-radius: 8px; }"
        )
        urls = event.mimeData().urls()
        paths = [u.toLocalFile() for u in urls if u.toLocalFile()]
        if paths:
            self.files_dropped.emit(paths)
        event.acceptProposedAction()
