"""
Main application window: sidebar navigation + stacked content panels.
"""
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QLabel, QPushButton, QComboBox, QFrame, QStackedWidget,
    QStatusBar, QSizePolicy, QSpacerItem, QMessageBox
)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QFont, QIcon

from PyQt6.QtWidgets import QApplication
from app.config import APP_NAME, APP_VERSION
from app.ui.styles import get_style
import app.db.repositories.veteran_repo as veteran_repo
from app.db.schema import get_setting, set_setting


from app.ui.panels.veteran_panel import VeteranPanel
from app.ui.panels.document_panel import DocumentPanel
from app.ui.panels.search_panel import SearchPanel
from app.ui.panels.claim_panel import ClaimPanel
from app.ui.panels.dashboard_panel import DashboardPanel
from app.ui.panels.export_panel import ExportPanel
from app.ui.panels.conditions_browser_panel import ConditionsBrowserPanel


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} v{APP_VERSION}")
        self.setMinimumSize(1100, 700)
        # Apply saved theme (dark/light) — reads DB before UI is built
        _saved_theme = get_setting("theme", "light")
        QApplication.instance().setStyleSheet(get_style(dark=(_saved_theme == "dark")))

        self._active_veteran_id: int | None = None
        self._nav_buttons: list[QPushButton] = []

        # Try to restore last used veteran (verify they still exist in DB)
        saved_vid = get_setting("active_veteran_id", "")
        if saved_vid.isdigit():
            vid = int(saved_vid)
            if veteran_repo.get_by_id(vid) is not None:
                self._active_veteran_id = vid
            else:
                # Veteran was deleted — clear the stale setting
                set_setting("active_veteran_id", "")

        self._build_ui()
        self._refresh_veteran_selector()
        self._restore_geometry()
        self._nav_select(0)   # Show dashboard by default

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ---- Left sidebar ----
        sidebar = QWidget()
        sidebar.setObjectName("sidebar")
        sidebar.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        sb_layout = QVBoxLayout(sidebar)
        sb_layout.setContentsMargins(0, 0, 0, 0)
        sb_layout.setSpacing(0)

        # App title
        title_lbl = QLabel(APP_NAME)
        title_lbl.setObjectName("app_title")
        title_lbl.setWordWrap(True)
        sb_layout.addWidget(title_lbl)

        ver_lbl = QLabel(f"v{APP_VERSION}")
        ver_lbl.setObjectName("app_subtitle")
        sb_layout.addWidget(ver_lbl)

        # Divider
        div1 = QFrame()
        div1.setObjectName("sidebar_divider")
        div1.setFrameShape(QFrame.Shape.HLine)
        sb_layout.addWidget(div1)

        # Veteran selector
        vet_box = QFrame()
        vet_box.setObjectName("veteran_selector")
        vet_vl = QVBoxLayout(vet_box)
        vet_vl.setContentsMargins(8, 6, 8, 6)
        vet_vl.setSpacing(4)

        vet_lbl = QLabel("Active Veteran")
        vet_lbl.setStyleSheet("color: #a0bdd8; font-size: 11px; background: transparent;")
        vet_vl.addWidget(vet_lbl)

        self._veteran_combo = QComboBox()
        self._veteran_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._veteran_combo.currentIndexChanged.connect(self._on_veteran_selected)
        vet_vl.addWidget(self._veteran_combo)
        sb_layout.addWidget(vet_box)

        # Divider
        div2 = QFrame()
        div2.setObjectName("sidebar_divider")
        div2.setFrameShape(QFrame.Shape.HLine)
        sb_layout.addWidget(div2)

        # Navigation buttons
        nav_items = [
            ("Dashboard", "dashboard"),
            ("Veteran Profile", "veteran"),
            ("Documents", "documents"),
            ("Claims", "claims"),
            ("Conditions", "conditions"),
            ("Search", "search"),
            ("Export Package", "export"),
        ]

        for i, (label, key) in enumerate(nav_items):
            btn = QPushButton(f"  {label}")
            btn.setProperty("nav_index", i)
            btn.setProperty("selected", False)
            btn.clicked.connect(lambda checked, idx=i: self._nav_select(idx))
            self._nav_buttons.append(btn)
            sb_layout.addWidget(btn)

        sb_layout.addStretch()

        # Bottom: settings
        div3 = QFrame()
        div3.setObjectName("sidebar_divider")
        div3.setFrameShape(QFrame.Shape.HLine)
        sb_layout.addWidget(div3)

        settings_btn = QPushButton("  Settings")
        settings_btn.clicked.connect(self._open_settings)
        sb_layout.addWidget(settings_btn)

        help_btn = QPushButton("  Help / About")
        help_btn.clicked.connect(self._open_about)
        sb_layout.addWidget(help_btn)

        root.addWidget(sidebar)

        # ---- Main content stack ----
        self._stack = QStackedWidget()
        self._stack.setObjectName("content_stack")
        root.addWidget(self._stack)

        # Build panels
        self._panels = {}
        self._build_panels()

        # Status bar
        self._status = QStatusBar()
        self._status.showMessage("Ready")
        self.setStatusBar(self._status)

    def _build_panels(self):
        """Instantiate and register all panels into the stack."""
        # 0: Dashboard
        dashboard = DashboardPanel()
        dashboard.add_claim_requested.connect(self._on_add_claim_from_browser)
        self._panels["dashboard"] = dashboard
        self._stack.addWidget(dashboard)

        # 1: Veteran Profile
        veteran_panel = VeteranPanel()
        veteran_panel.veteran_saved.connect(self._on_veteran_saved)
        veteran_panel.veteran_deleted.connect(self._on_veteran_deleted)
        self._panels["veteran"] = veteran_panel
        self._stack.addWidget(veteran_panel)

        # 2: Documents
        doc_panel = DocumentPanel()
        doc_panel.documents_updated.connect(self._on_data_updated)
        self._panels["documents"] = doc_panel
        self._stack.addWidget(doc_panel)

        # 3: Claims
        claim_panel = ClaimPanel()
        claim_panel.claims_updated.connect(self._on_data_updated)
        self._panels["claims"] = claim_panel
        self._stack.addWidget(claim_panel)

        # 4: Conditions Browser
        conditions_panel = ConditionsBrowserPanel()
        conditions_panel.add_claim_requested.connect(self._on_add_claim_from_browser)
        self._panels["conditions"] = conditions_panel
        self._stack.addWidget(conditions_panel)

        # 5: Search
        search_panel = SearchPanel()
        self._panels["search"] = search_panel
        self._stack.addWidget(search_panel)

        # 6: Export
        export_panel = ExportPanel()
        self._panels["export"] = export_panel
        self._stack.addWidget(export_panel)

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    def _nav_select(self, index: int):
        for i, btn in enumerate(self._nav_buttons):
            btn.setProperty("selected", i == index)
            btn.style().unpolish(btn)
            btn.style().polish(btn)
        self._stack.setCurrentIndex(index)
        keys = ["dashboard", "veteran", "documents", "claims", "conditions", "search", "export"]
        if 0 <= index < len(keys):
            panel_key = keys[index]
            vid = self._active_veteran_id
            if panel_key == "veteran":
                vp = self._panels.get("veteran")
                if isinstance(vp, VeteranPanel):
                    vp.load_veteran(vid)
            elif panel_key == "documents":
                dp = self._panels.get("documents")
                if isinstance(dp, DocumentPanel):
                    dp.load_veteran(vid)
            elif panel_key == "claims":
                cp = self._panels.get("claims")
                if isinstance(cp, ClaimPanel):
                    cp.load_veteran(vid)
            elif panel_key == "conditions":
                cbp = self._panels.get("conditions")
                if isinstance(cbp, ConditionsBrowserPanel):
                    cbp.load_veteran(vid)
            elif panel_key == "search":
                sp = self._panels.get("search")
                if isinstance(sp, SearchPanel):
                    sp.load_veteran(vid)
            elif panel_key == "dashboard":
                dash = self._panels.get("dashboard")
                if isinstance(dash, DashboardPanel):
                    dash.load_veteran(vid)

    # ------------------------------------------------------------------
    # Veteran selector
    # ------------------------------------------------------------------

    def _refresh_veteran_selector(self):
        self._veteran_combo.blockSignals(True)
        self._veteran_combo.clear()
        self._veteran_combo.addItem("-- No Veteran Selected --", None)

        veterans = veteran_repo.get_all()
        selected_idx = 0
        for i, v in enumerate(veterans):
            self._veteran_combo.addItem(v.display_name, v.id)
            if v.id == self._active_veteran_id:
                selected_idx = i + 1

        self._veteran_combo.setCurrentIndex(selected_idx)
        self._veteran_combo.blockSignals(False)

    def _on_veteran_selected(self, index: int):
        vid = self._veteran_combo.itemData(index)
        self._active_veteran_id = vid
        set_setting("active_veteran_id", str(vid) if vid else "")

        # Propagate new veteran to all active panels
        for key, panel in self._panels.items():
            if hasattr(panel, "load_veteran"):
                panel.load_veteran(vid)

        if vid:
            v = veteran_repo.get_by_id(vid)
            if v:
                self._status.showMessage(f"Active veteran: {v.display_name}  |  {v.service_summary}")
        else:
            self._status.showMessage("No veteran selected")

    def _on_veteran_saved(self, veteran_id: int):
        self._active_veteran_id = veteran_id
        self._refresh_veteran_selector()
        # Select the saved veteran in combo
        idx = self._veteran_combo.findData(veteran_id)
        if idx >= 0:
            self._veteran_combo.blockSignals(True)
            self._veteran_combo.setCurrentIndex(idx)
            self._veteran_combo.blockSignals(False)
        v = veteran_repo.get_by_id(veteran_id)
        if v:
            self._status.showMessage(f"Saved: {v.display_name}")

    def _on_veteran_deleted(self):
        self._active_veteran_id = None
        self._refresh_veteran_selector()
        self._status.showMessage("Veteran deleted")

    def _on_data_updated(self):
        """Refresh the dashboard whenever documents or claims change."""
        dash = self._panels.get("dashboard")
        if isinstance(dash, DashboardPanel):
            dash.refresh()

    def _on_add_claim_from_browser(self, condition: dict):
        """Navigate to Claims panel and pre-fill editor with the selected condition."""
        self._nav_select(3)  # Claims is index 3
        cp = self._panels.get("claims")
        if isinstance(cp, ClaimPanel):
            cp.prefill_new_claim(condition)

    # ------------------------------------------------------------------
    # Dialogs
    # ------------------------------------------------------------------

    def _open_settings(self):
        from app.ui.dialogs.settings_dialog import SettingsDialog
        dlg = SettingsDialog(self)
        dlg.exec()

    def _open_about(self):
        QMessageBox.about(
            self, f"About {APP_NAME}",
            f"<b>{APP_NAME}</b><br>"
            f"Version {APP_VERSION}<br><br>"
            "Helps US Military Veterans organize medical records and "
            "apply for VA Disability compensation.<br><br>"
            "Built on the Caluza Triangle framework:<br>"
            "Current Diagnosis + In-Service Event + Medical Nexus<br><br>"
            "<i>Not a substitute for professional legal or medical advice.<br>"
            "Always consult a VSO or accredited VA attorney.</i>"
        )

    # ------------------------------------------------------------------
    # Geometry persistence
    # ------------------------------------------------------------------

    def _restore_geometry(self):
        geom = get_setting("window_geometry", "")
        if geom:
            from PyQt6.QtCore import QByteArray
            self.restoreGeometry(QByteArray.fromBase64(geom.encode()))
        else:
            self.resize(1200, 780)
            self._center_on_screen()

    def _center_on_screen(self):
        screen = self.screen()
        if screen:
            rect = screen.availableGeometry()
            self.move(
                (rect.width() - self.width()) // 2,
                (rect.height() - self.height()) // 2,
            )

    def closeEvent(self, event):
        geom_b64 = self.saveGeometry().toBase64().data().decode()
        set_setting("window_geometry", geom_b64)
        super().closeEvent(event)

    # ------------------------------------------------------------------
    # Placeholder helper
    # ------------------------------------------------------------------

    @staticmethod
    def _make_placeholder_panel(title: str, description: str) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(48, 48, 48, 48)
        layout.setSpacing(16)

        title_lbl = QLabel(title)
        title_lbl.setObjectName("section_header")
        layout.addWidget(title_lbl)

        desc_lbl = QLabel(description)
        desc_lbl.setWordWrap(True)
        desc_lbl.setStyleSheet("color: #555e6e; font-size: 14px; line-height: 1.6;")
        layout.addWidget(desc_lbl)

        coming_lbl = QLabel("This panel will be available in the next build phase.")
        coming_lbl.setStyleSheet(
            "color: #b8610a; font-size: 13px; font-style: italic; margin-top: 8px;"
        )
        layout.addWidget(coming_lbl)
        layout.addStretch()
        return w
