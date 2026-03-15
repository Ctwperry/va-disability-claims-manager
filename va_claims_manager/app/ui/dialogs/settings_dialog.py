"""
Application Settings Dialog.

Sections:
  Appearance  — Dark Mode toggle (applied live, no restart)
  OCR         — Tesseract executable path
  Export      — Default output directory
  Performance — Parallel ingestion workers (1–8)

All settings are persisted to the app_settings SQLite table via get/set_setting.
"""
from __future__ import annotations

from pathlib import Path

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QCheckBox, QSpinBox, QFrame, QFileDialog,
    QGroupBox, QFormLayout, QDialogButtonBox, QApplication,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont

from app.db.schema import get_setting, set_setting
from app.ingestion.pipeline import MAX_EXTRACTION_WORKERS


class SettingsDialog(QDialog):
    """
    Modal settings dialog.

    Emits `theme_changed(is_dark: bool)` when the user applies a theme switch
    so the main window can update its title-bar or other chrome if needed.
    (The stylesheet is applied to QApplication directly, so all widgets update
    automatically without any additional wiring.)
    """

    theme_changed = pyqtSignal(bool)   # True = dark, False = light

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setMinimumWidth(520)
        self.setModal(True)

        self._original_theme = get_setting("theme", "light")
        self._build_ui()
        self._load_settings()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(14)

        title = QLabel("Settings")
        title.setObjectName("section_header")
        layout.addWidget(title)

        # ---- Appearance ----
        app_group = QGroupBox("Appearance")
        app_form = QVBoxLayout(app_group)
        app_form.setContentsMargins(12, 12, 12, 12)
        app_form.setSpacing(8)

        self._dark_cb = QCheckBox("Dark Mode  (reduces eye strain, especially at night)")
        self._dark_cb.stateChanged.connect(self._preview_theme)
        app_form.addWidget(self._dark_cb)

        hint = QLabel("Theme change applies immediately — no restart required.")
        hint.setStyleSheet("color: #888; font-size: 11px;")
        app_form.addWidget(hint)

        layout.addWidget(app_group)

        # ---- OCR Configuration ----
        ocr_group = QGroupBox("OCR Configuration")
        ocr_layout = QVBoxLayout(ocr_group)
        ocr_layout.setContentsMargins(12, 12, 12, 12)
        ocr_layout.setSpacing(8)

        ocr_lbl = QLabel("Tesseract OCR Executable Path:")
        ocr_lbl.setStyleSheet("font-size: 12px; font-weight: bold;")
        ocr_layout.addWidget(ocr_lbl)

        tess_row = QHBoxLayout()
        self._tess_path = QLineEdit()
        self._tess_path.setPlaceholderText("Auto-detect  (leave blank for default paths)")
        tess_row.addWidget(self._tess_path)

        browse_tess = QPushButton("Browse…")
        browse_tess.setObjectName("secondary_btn")
        browse_tess.setFixedWidth(80)
        browse_tess.clicked.connect(self._browse_tesseract)
        tess_row.addWidget(browse_tess)
        ocr_layout.addLayout(tess_row)

        ocr_hint = QLabel(
            "Default search paths:  C:\\Program Files\\Tesseract-OCR\\tesseract.exe\n"
            "Install via:  winget install UB-Mannheim.TesseractOCR"
        )
        ocr_hint.setStyleSheet("color: #888; font-size: 11px;")
        ocr_layout.addWidget(ocr_hint)

        layout.addWidget(ocr_group)

        # ---- Export ----
        exp_group = QGroupBox("Export")
        exp_layout = QVBoxLayout(exp_group)
        exp_layout.setContentsMargins(12, 12, 12, 12)
        exp_layout.setSpacing(8)

        exp_lbl = QLabel("Default Export Directory:")
        exp_lbl.setStyleSheet("font-size: 12px; font-weight: bold;")
        exp_layout.addWidget(exp_lbl)

        dir_row = QHBoxLayout()
        self._export_dir = QLineEdit()
        self._export_dir.setPlaceholderText("Leave blank to use  data/exports/  (recommended)")
        dir_row.addWidget(self._export_dir)

        browse_dir = QPushButton("Browse…")
        browse_dir.setObjectName("secondary_btn")
        browse_dir.setFixedWidth(80)
        browse_dir.clicked.connect(self._browse_export_dir)
        dir_row.addWidget(browse_dir)
        exp_layout.addLayout(dir_row)

        layout.addWidget(exp_group)

        # ---- Performance ----
        perf_group = QGroupBox("Performance")
        perf_layout = QVBoxLayout(perf_group)
        perf_layout.setContentsMargins(12, 12, 12, 12)
        perf_layout.setSpacing(8)

        workers_row = QHBoxLayout()
        workers_lbl = QLabel("Parallel ingestion workers:")
        workers_lbl.setStyleSheet("font-size: 12px;")
        workers_row.addWidget(workers_lbl)

        self._workers_spin = QSpinBox()
        self._workers_spin.setRange(1, 8)
        self._workers_spin.setValue(MAX_EXTRACTION_WORKERS)
        self._workers_spin.setFixedWidth(60)
        self._workers_spin.setToolTip(
            "Number of files processed in parallel during document import.\n"
            "4 is optimal for most systems.  Reduce to 1–2 if OCR causes\n"
            "high CPU/memory usage."
        )
        workers_row.addWidget(self._workers_spin)
        workers_row.addStretch()
        perf_layout.addLayout(workers_row)

        perf_hint = QLabel(
            "Higher = faster batch imports.  Lower = less CPU/memory pressure.\n"
            "Recommended: 4  (2 for older hardware, 6–8 for SSD + 16GB+ RAM)"
        )
        perf_hint.setStyleSheet("color: #888; font-size: 11px;")
        perf_layout.addWidget(perf_hint)

        layout.addWidget(perf_group)

        # ---- Button row ----
        layout.addSpacing(4)
        btn_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        btn_box.accepted.connect(self._on_ok)
        btn_box.rejected.connect(self._on_cancel)
        layout.addWidget(btn_box)

    # ------------------------------------------------------------------
    # Load / Save
    # ------------------------------------------------------------------

    def _load_settings(self):
        """Populate widgets from DB."""
        theme = get_setting("theme", "light")
        self._dark_cb.setChecked(theme == "dark")

        tess = get_setting("tesseract_path", "")
        self._tess_path.setText(tess)

        exp_dir = get_setting("default_export_dir", "")
        self._export_dir.setText(exp_dir)

        try:
            workers = int(get_setting("max_ingestion_workers",
                                      str(MAX_EXTRACTION_WORKERS)))
        except ValueError:
            workers = MAX_EXTRACTION_WORKERS
        self._workers_spin.setValue(max(1, min(8, workers)))

    def _on_ok(self):
        """Save all settings and close."""
        self._save_all()
        self.accept()

    def _on_cancel(self):
        """Revert any live theme preview and close."""
        if self._original_theme != ("dark" if self._dark_cb.isChecked() else "light"):
            original_dark = self._original_theme == "dark"
            self._apply_theme(original_dark)
        self.reject()

    def _save_all(self):
        is_dark = self._dark_cb.isChecked()
        set_setting("theme", "dark" if is_dark else "light")
        set_setting("tesseract_path", self._tess_path.text().strip())
        set_setting("default_export_dir", self._export_dir.text().strip())
        set_setting("max_ingestion_workers", str(self._workers_spin.value()))
        self.theme_changed.emit(is_dark)

    # ------------------------------------------------------------------
    # Live theme preview
    # ------------------------------------------------------------------

    def _preview_theme(self):
        """Apply theme immediately as the user toggles the checkbox."""
        self._apply_theme(self._dark_cb.isChecked())

    @staticmethod
    def _apply_theme(dark: bool):
        from app.ui.styles import get_style
        app = QApplication.instance()
        if app:
            app.setStyleSheet(get_style(dark=dark))

    # ------------------------------------------------------------------
    # File browsers
    # ------------------------------------------------------------------

    def _browse_tesseract(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Tesseract Executable",
            r"C:\Program Files\Tesseract-OCR",
            "Executables (*.exe);;All Files (*)",
        )
        if path:
            self._tess_path.setText(path)

    def _browse_export_dir(self):
        current = self._export_dir.text().strip() or str(Path.home())
        path = QFileDialog.getExistingDirectory(
            self, "Select Default Export Directory", current
        )
        if path:
            self._export_dir.setText(path)
