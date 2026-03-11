"""
Full-text search panel with FTS5 results and highlighted snippets.
"""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QListWidget, QListWidgetItem, QFrame,
    QComboBox, QTextBrowser, QSplitter, QSizePolicy,
    QMessageBox
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QFont, QColor

from app.config import DOC_TYPES
from app.ui.workers import SearchWorker, get_thread_pool
from app.search.fts_engine import SearchResult, get_page_text


class SearchPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._veteran_id: int | None = None
        self._results: list[SearchResult] = []
        self._search_timer = QTimer()
        self._search_timer.setSingleShot(True)
        self._search_timer.timeout.connect(self._execute_search)
        self._build_ui()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)

        # Header
        title = QLabel("Document Search")
        title.setObjectName("section_header")
        layout.addWidget(title)

        hint = QLabel(
            'Search across all imported documents. '
            'Use quotes for exact phrases: <b>"at least as likely as not"</b>  |  '
            'Results are ranked by relevance (Porter stemming — "diagnosed" matches "diagnosis").'
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #555e6e; font-size: 12px;")
        hint.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(hint)

        # Search bar row
        search_row = QHBoxLayout()

        self._search_box = QLineEdit()
        self._search_box.setObjectName("search_bar")
        self._search_box.setPlaceholderText('Search medical records...  e.g. "nexus" or "lumbar disc"')
        self._search_box.returnPressed.connect(self._execute_search)
        self._search_box.textChanged.connect(self._on_text_changed)
        search_row.addWidget(self._search_box)

        self._btn_search = QPushButton("Search")
        self._btn_search.setFixedWidth(90)
        self._btn_search.clicked.connect(self._execute_search)
        search_row.addWidget(self._btn_search)

        layout.addLayout(search_row)

        # Filter row
        filter_row = QHBoxLayout()
        filter_row.addWidget(QLabel("Filter by type:"))

        self._type_filter = QComboBox()
        self._type_filter.addItem("All Document Types", "")
        for key, label in DOC_TYPES.items():
            self._type_filter.addItem(label, key)
        self._type_filter.setFixedWidth(240)
        self._type_filter.currentIndexChanged.connect(self._execute_search)
        filter_row.addWidget(self._type_filter)
        filter_row.addStretch()

        self._result_count_lbl = QLabel("")
        self._result_count_lbl.setStyleSheet("color: #555e6e; font-size: 12px;")
        filter_row.addWidget(self._result_count_lbl)

        layout.addLayout(filter_row)

        # Splitter: results list (left) + page viewer (right)
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Results list
        results_widget = QWidget()
        results_layout = QVBoxLayout(results_widget)
        results_layout.setContentsMargins(0, 0, 0, 0)
        results_layout.setSpacing(4)

        results_label = QLabel("Results")
        results_label.setObjectName("subsection_header")
        results_layout.addWidget(results_label)

        self._results_list = QListWidget()
        self._results_list.setSpacing(2)
        self._results_list.currentItemChanged.connect(self._on_result_selected)
        results_layout.addWidget(self._results_list)

        splitter.addWidget(results_widget)

        # Page viewer
        viewer_widget = QWidget()
        viewer_layout = QVBoxLayout(viewer_widget)
        viewer_layout.setContentsMargins(0, 0, 0, 0)
        viewer_layout.setSpacing(4)

        viewer_label = QLabel("Page Content")
        viewer_label.setObjectName("subsection_header")
        viewer_layout.addWidget(viewer_label)

        self._doc_info = QLabel("")
        self._doc_info.setStyleSheet("color: #555e6e; font-size: 11px;")
        viewer_layout.addWidget(self._doc_info)

        self._page_viewer = QTextBrowser()
        self._page_viewer.setOpenLinks(False)
        self._page_viewer.setStyleSheet(
            "QTextBrowser { background-color: #ffffff; border: 1px solid #dde2e8; "
            "border-radius: 6px; padding: 12px; font-family: 'Segoe UI', sans-serif; "
            "font-size: 13px; line-height: 1.6; }"
        )
        viewer_layout.addWidget(self._page_viewer)

        splitter.addWidget(viewer_widget)
        splitter.setSizes([380, 680])

        layout.addWidget(splitter)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load_veteran(self, veteran_id: int | None):
        self._veteran_id = veteran_id
        self._results_list.clear()
        self._page_viewer.clear()
        self._result_count_lbl.setText("")

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _on_text_changed(self, text: str):
        # Debounce: run search 400ms after the user stops typing
        if len(text) >= 2:
            self._search_timer.start(400)

    def _execute_search(self):
        self._search_timer.stop()
        query = self._search_box.text().strip()
        if not query or not self._veteran_id:
            return

        self._btn_search.setEnabled(False)
        self._btn_search.setText("...")
        self._result_count_lbl.setText("Searching...")

        doc_type = self._type_filter.currentData() or None

        worker = SearchWorker(query, self._veteran_id, doc_type_filter=doc_type)
        worker.signals.result.connect(self._on_search_done)
        worker.signals.error.connect(self._on_search_error)
        get_thread_pool().start(worker)

    def _on_search_done(self, results: list):
        self._btn_search.setEnabled(True)
        self._btn_search.setText("Search")
        self._results = results
        self._populate_results()

    def _on_search_error(self, error: str):
        self._btn_search.setEnabled(True)
        self._btn_search.setText("Search")
        self._result_count_lbl.setText("Search error")
        QMessageBox.warning(self, "Search Error", f"Search failed:\n\n{error[:400]}")

    def _populate_results(self):
        self._results_list.clear()
        self._page_viewer.clear()
        self._doc_info.setText("")

        count = len(self._results)
        self._result_count_lbl.setText(
            f"{count} result{'s' if count != 1 else ''} found"
        )

        for result in self._results:
            # Build list item text
            doc_type_label = DOC_TYPES.get(result.doc_type, result.doc_type)
            date_str = f"  ({result.doc_date})" if result.doc_date else ""

            # Strip HTML tags from snippet for list display
            import re
            plain_snippet = re.sub(r"<[^>]+>", "", result.snippet).strip()
            plain_snippet = plain_snippet[:120] + "..." if len(plain_snippet) > 120 else plain_snippet

            display = (
                f"{result.filename}  —  p.{result.page_number}"
                f"\n[{doc_type_label}]{date_str}"
                f"\n{plain_snippet}"
            )

            item = QListWidgetItem(display)
            item.setData(Qt.ItemDataRole.UserRole, result)
            item.setFont(QFont("Segoe UI", 11))
            self._results_list.addItem(item)

    def _on_result_selected(self, current: QListWidgetItem, _):
        if current is None:
            return
        result: SearchResult = current.data(Qt.ItemDataRole.UserRole)
        if result is None:
            return

        # Update doc info
        doc_type_label = DOC_TYPES.get(result.doc_type, result.doc_type)
        self._doc_info.setText(
            f"{result.filename}  |  Page {result.page_number}  |  "
            f"{doc_type_label}  |  {result.doc_date or 'No date'}"
        )

        # Load full page text
        full_text = get_page_text(result.page_id)
        if not full_text:
            self._page_viewer.setHtml("<i>Page text not available.</i>")
            return

        # Highlight search terms in the full page text
        query = self._search_box.text().strip()
        html = self._highlight_text(full_text, query)
        self._page_viewer.setHtml(
            f"<html><body style='font-family:Segoe UI,sans-serif; font-size:13px; "
            f"line-height:1.7; color:#1a1a2e; white-space:pre-wrap;'>{html}</body></html>"
        )

    @staticmethod
    def _highlight_text(text: str, query: str) -> str:
        """Highlight query terms in plain text, return HTML."""
        import html as html_lib
        import re

        escaped_text = html_lib.escape(text)

        # Extract search terms (remove FTS5 operators and quotes)
        terms = re.findall(r'[a-zA-Z]{2,}', query)
        for term in set(terms):
            if len(term) < 2:
                continue
            pattern = re.compile(re.escape(term), re.IGNORECASE)
            escaped_text = pattern.sub(
                lambda m: f'<mark style="background-color:#fff176;color:#1a1a2e;">{m.group()}</mark>',
                escaped_text,
            )
        return escaped_text.replace("\n", "<br>")
