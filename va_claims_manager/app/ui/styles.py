"""
Application-wide QSS stylesheets — light (default) and dark themes.

Public API:
    get_style(dark: bool = False) -> str   — returns appropriate QSS string
    MAIN_STYLE                              — light stylesheet constant
    DARK_STYLE                              — dark stylesheet constant
    COLOR_* constants                       — for Python-side use (QPainter, etc.)
"""

# ---------------------------------------------------------------------------
# Light theme (default)
# ---------------------------------------------------------------------------

MAIN_STYLE = """
/* ===== Global ===== */
QWidget {
    font-family: "Segoe UI", Arial, sans-serif;
    font-size: 13px;
    color: #1a1a2e;
    background-color: #f0f2f5;
}

QMainWindow {
    background-color: #f0f2f5;
}

/* ===== Sidebar ===== */
#sidebar {
    background-color: #003366;
    min-width: 220px;
    max-width: 220px;
    border-right: 1px solid #00254d;
}

#sidebar QLabel#app_title {
    color: #ffffff;
    font-size: 15px;
    font-weight: bold;
    padding: 16px 16px 4px 16px;
    background-color: transparent;
}

#sidebar QLabel#app_subtitle {
    color: #a0bdd8;
    font-size: 11px;
    padding: 0px 16px 16px 16px;
    background-color: transparent;
}

#sidebar QPushButton {
    background-color: transparent;
    color: #c8daf0;
    border: none;
    text-align: left;
    padding: 10px 16px;
    font-size: 13px;
    border-radius: 0px;
}

#sidebar QPushButton:hover {
    background-color: #004080;
    color: #ffffff;
}

#sidebar QPushButton[selected="true"] {
    background-color: #0070c0;
    color: #ffffff;
    font-weight: bold;
    border-left: 3px solid #66b2ff;
}

#sidebar_divider {
    background-color: #004a8c;
    min-height: 1px;
    max-height: 1px;
    margin: 6px 12px;
}

#veteran_selector {
    background-color: #004a8c;
    border-radius: 6px;
    margin: 8px;
    padding: 4px;
}

#veteran_selector QComboBox {
    background-color: transparent;
    color: #ffffff;
    border: 1px solid #336699;
    border-radius: 4px;
    padding: 4px 8px;
    font-size: 12px;
}

#veteran_selector QComboBox::drop-down {
    border: none;
    width: 20px;
}

#veteran_selector QComboBox QAbstractItemView {
    background-color: #003366;
    color: #ffffff;
    selection-background-color: #0070c0;
}

/* ===== Content area ===== */
#content_stack {
    background-color: #f0f2f5;
}

/* ===== Cards / Panels ===== */
QFrame#card {
    background-color: #ffffff;
    border-radius: 8px;
    border: 1px solid #dde2e8;
}

/* ===== Section headers ===== */
QLabel#section_header {
    font-size: 16px;
    font-weight: bold;
    color: #003366;
    padding-bottom: 4px;
}

QLabel#subsection_header {
    font-size: 13px;
    font-weight: bold;
    color: #003366;
    padding: 6px 0px 2px 0px;
}

QLabel#field_label {
    color: #555e6e;
    font-size: 12px;
}

/* ===== Inputs ===== */
QLineEdit, QTextEdit, QPlainTextEdit {
    background-color: #ffffff;
    border: 1px solid #c8d0d9;
    border-radius: 4px;
    padding: 5px 8px;
    color: #1a1a2e;
    selection-background-color: #0070c0;
}

QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {
    border: 1px solid #0070c0;
    outline: none;
}

QComboBox {
    background-color: #ffffff;
    border: 1px solid #c8d0d9;
    border-radius: 4px;
    padding: 5px 8px;
    color: #1a1a2e;
}

QComboBox:focus {
    border: 1px solid #0070c0;
}

QComboBox::drop-down {
    border: none;
    width: 24px;
}

QComboBox QAbstractItemView {
    background-color: #ffffff;
    border: 1px solid #c8d0d9;
    selection-background-color: #e3f0ff;
    selection-color: #003366;
}

QDateEdit {
    background-color: #ffffff;
    border: 1px solid #c8d0d9;
    border-radius: 4px;
    padding: 5px 8px;
    color: #1a1a2e;
}

QDateEdit:focus {
    border: 1px solid #0070c0;
}

QCheckBox {
    spacing: 6px;
    color: #1a1a2e;
}

QCheckBox::indicator {
    width: 16px;
    height: 16px;
    border: 1px solid #c8d0d9;
    border-radius: 3px;
    background-color: #ffffff;
}

QCheckBox::indicator:checked {
    background-color: #0070c0;
    border-color: #0070c0;
}

/* ===== Buttons ===== */
QPushButton {
    background-color: #0070c0;
    color: #ffffff;
    border: none;
    border-radius: 5px;
    padding: 7px 16px;
    font-size: 13px;
    font-weight: 500;
}

QPushButton:hover {
    background-color: #005a9e;
}

QPushButton:pressed {
    background-color: #004480;
}

QPushButton:disabled {
    background-color: #c8d0d9;
    color: #8a939f;
}

QPushButton#secondary_btn {
    background-color: transparent;
    color: #0070c0;
    border: 1px solid #0070c0;
}

QPushButton#secondary_btn:hover {
    background-color: #e3f0ff;
}

QPushButton#danger_btn {
    background-color: #c0392b;
}

QPushButton#danger_btn:hover {
    background-color: #a93226;
}

QPushButton#success_btn {
    background-color: #1a7a4a;
}

QPushButton#success_btn:hover {
    background-color: #145e38;
}

/* ===== Tables ===== */
QTableWidget {
    background-color: #ffffff;
    gridline-color: #eaedf1;
    border: 1px solid #dde2e8;
    border-radius: 6px;
    selection-background-color: #e3f0ff;
    selection-color: #003366;
}

QTableWidget::item {
    padding: 6px 8px;
    border-bottom: 1px solid #f0f2f5;
}

QTableWidget::item:selected {
    background-color: #e3f0ff;
    color: #003366;
}

QHeaderView::section {
    background-color: #f5f7fa;
    color: #555e6e;
    font-weight: bold;
    font-size: 12px;
    padding: 6px 8px;
    border: none;
    border-bottom: 2px solid #dde2e8;
}

/* ===== Scroll bars ===== */
QScrollBar:vertical {
    width: 10px;
    background: #f0f2f5;
    border-radius: 5px;
}

QScrollBar::handle:vertical {
    background: #c8d0d9;
    border-radius: 5px;
    min-height: 30px;
}

QScrollBar::handle:vertical:hover {
    background: #0070c0;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}

QScrollBar:horizontal {
    height: 10px;
    background: #f0f2f5;
    border-radius: 5px;
}

QScrollBar::handle:horizontal {
    background: #c8d0d9;
    border-radius: 5px;
    min-width: 30px;
}

QScrollBar::handle:horizontal:hover {
    background: #0070c0;
}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0px;
}

/* ===== Status bar ===== */
QStatusBar {
    background-color: #003366;
    color: #a0bdd8;
    font-size: 12px;
    border-top: 1px solid #00254d;
}

/* ===== Splitters ===== */
QSplitter::handle {
    background-color: #dde2e8;
}

QSplitter::handle:horizontal {
    width: 2px;
}

QSplitter::handle:vertical {
    height: 2px;
}

/* ===== Tab widget ===== */
QTabWidget::pane {
    border: none;
    background-color: #ffffff;
    border-radius: 0px 8px 8px 8px;
}

QTabBar::tab {
    background-color: #dde2e8;
    color: #555e6e;
    padding: 7px 18px;
    border-radius: 6px 6px 0px 0px;
    margin-right: 2px;
    font-size: 12px;
}

QTabBar::tab:selected {
    background-color: #ffffff;
    color: #003366;
    font-weight: bold;
}

QTabBar::tab:hover:!selected {
    background-color: #c8d0d9;
}

/* ===== Progress bar ===== */
QProgressBar {
    background-color: #dde2e8;
    border-radius: 4px;
    text-align: center;
    font-size: 11px;
    color: #1a1a2e;
    min-height: 16px;
    max-height: 16px;
}

QProgressBar::chunk {
    background-color: #0070c0;
    border-radius: 4px;
}

/* ===== Search bar ===== */
QLineEdit#search_bar {
    background-color: #ffffff;
    border: 2px solid #0070c0;
    border-radius: 20px;
    padding: 8px 16px;
    font-size: 14px;
    color: #1a1a2e;
}

QLineEdit#search_bar:focus {
    border: 2px solid #003366;
}

/* ===== Tooltips ===== */
QToolTip {
    background-color: #1a1a2e;
    color: #ffffff;
    border: none;
    padding: 4px 8px;
    border-radius: 4px;
    font-size: 12px;
}

/* ===== Message boxes ===== */
QMessageBox {
    background-color: #ffffff;
}

/* ===== List widget ===== */
QListWidget {
    background-color: #ffffff;
    border: 1px solid #dde2e8;
    border-radius: 6px;
    outline: none;
}

QListWidget::item {
    padding: 8px 12px;
    border-bottom: 1px solid #f0f2f5;
    color: #1a1a2e;
}

QListWidget::item:selected {
    background-color: #e3f0ff;
    color: #003366;
}

QListWidget::item:hover:!selected {
    background-color: #f5f7fa;
}

/* ===== Group boxes ===== */
QGroupBox {
    border: 1px solid #dde2e8;
    border-radius: 6px;
    margin-top: 12px;
    padding: 8px;
    font-weight: bold;
    color: #003366;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0px 8px;
    margin-left: 8px;
    color: #003366;
    font-size: 12px;
    font-weight: bold;
}

/* ===== Named structural widgets ===== */
QWidget#claim_list_sidebar {
    background-color: #f8f9fb;
    border-right: 1px solid #dde2e8;
}

QWidget#table_header_row {
    background-color: #f5f7fa;
    border-bottom: 2px solid #dde2e8;
}

QFrame#filter_bar, QWidget#filter_bar {
    background-color: #f8f9fb;
    border-bottom: 1px solid #dde2e8;
}

QWidget#dialog_footer, QFrame#dialog_footer {
    background-color: #f8f9fb;
    border-top: 1px solid #dde2e8;
}

QWidget#dialog_input_frame, QFrame#dialog_input_frame {
    background-color: #f8f9fb;
    border-bottom: 1px solid #dde2e8;
}

QFrame#drop_zone {
    border: 2px dashed #0070c0;
    background-color: #f0f6ff;
    border-radius: 8px;
}

QFrame#banner_success {
    background-color: #e8f5e9;
    border: 1px solid #4caf50;
    border-radius: 8px;
}

QFrame#banner_warning {
    background-color: #fff8e1;
    border: 1px solid #ffc107;
    border-radius: 8px;
}
"""


# ---------------------------------------------------------------------------
# Dark theme
# ---------------------------------------------------------------------------

DARK_STYLE = """
/* ===== Global ===== */
QWidget {
    font-family: "Segoe UI", Arial, sans-serif;
    font-size: 13px;
    color: #e8ecf1;
    background-color: #1e2228;
}

QMainWindow {
    background-color: #1e2228;
}

/* ===== Sidebar ===== */
#sidebar {
    background-color: #12151a;
    min-width: 220px;
    max-width: 220px;
    border-right: 1px solid #0d1014;
}

#sidebar QLabel#app_title {
    color: #ffffff;
    font-size: 15px;
    font-weight: bold;
    padding: 16px 16px 4px 16px;
    background-color: transparent;
}

#sidebar QLabel#app_subtitle {
    color: #6b7a8d;
    font-size: 11px;
    padding: 0px 16px 16px 16px;
    background-color: transparent;
}

#sidebar QPushButton {
    background-color: transparent;
    color: #9aafca;
    border: none;
    text-align: left;
    padding: 10px 16px;
    font-size: 13px;
    border-radius: 0px;
}

#sidebar QPushButton:hover {
    background-color: #1e2a3a;
    color: #dce8f5;
}

#sidebar QPushButton[selected="true"] {
    background-color: #0070c0;
    color: #ffffff;
    font-weight: bold;
    border-left: 3px solid #66b2ff;
}

#sidebar_divider {
    background-color: #1e2530;
    min-height: 1px;
    max-height: 1px;
    margin: 6px 12px;
}

#veteran_selector {
    background-color: #1a2030;
    border-radius: 6px;
    margin: 8px;
    padding: 4px;
}

#veteran_selector QComboBox {
    background-color: transparent;
    color: #dce8f5;
    border: 1px solid #2d3a4a;
    border-radius: 4px;
    padding: 4px 8px;
    font-size: 12px;
}

#veteran_selector QComboBox::drop-down {
    border: none;
    width: 20px;
}

#veteran_selector QComboBox QAbstractItemView {
    background-color: #12151a;
    color: #dce8f5;
    selection-background-color: #0070c0;
}

/* ===== Content area ===== */
#content_stack {
    background-color: #1e2228;
}

/* ===== Cards / Panels ===== */
QFrame#card {
    background-color: #272c35;
    border-radius: 8px;
    border: 1px solid #343b47;
}

/* ===== Section headers ===== */
QLabel#section_header {
    font-size: 16px;
    font-weight: bold;
    color: #5aa8f0;
    padding-bottom: 4px;
}

QLabel#subsection_header {
    font-size: 13px;
    font-weight: bold;
    color: #5aa8f0;
    padding: 6px 0px 2px 0px;
}

QLabel#field_label {
    color: #8a95a3;
    font-size: 12px;
}

/* ===== Inputs ===== */
QLineEdit, QTextEdit, QPlainTextEdit {
    background-color: #2a2f3a;
    border: 1px solid #3a4252;
    border-radius: 4px;
    padding: 5px 8px;
    color: #e8ecf1;
    selection-background-color: #0070c0;
}

QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {
    border: 1px solid #3d9de8;
    outline: none;
}

QComboBox {
    background-color: #2a2f3a;
    border: 1px solid #3a4252;
    border-radius: 4px;
    padding: 5px 8px;
    color: #e8ecf1;
}

QComboBox:focus {
    border: 1px solid #3d9de8;
}

QComboBox::drop-down {
    border: none;
    width: 24px;
}

QComboBox QAbstractItemView {
    background-color: #2a2f3a;
    border: 1px solid #3a4252;
    selection-background-color: #1a3a5c;
    selection-color: #e8ecf1;
}

QDateEdit {
    background-color: #2a2f3a;
    border: 1px solid #3a4252;
    border-radius: 4px;
    padding: 5px 8px;
    color: #e8ecf1;
}

QDateEdit:focus {
    border: 1px solid #3d9de8;
}

QCheckBox {
    spacing: 6px;
    color: #e8ecf1;
}

QCheckBox::indicator {
    width: 16px;
    height: 16px;
    border: 1px solid #3a4252;
    border-radius: 3px;
    background-color: #2a2f3a;
}

QCheckBox::indicator:checked {
    background-color: #0070c0;
    border-color: #0070c0;
}

/* ===== Buttons ===== */
QPushButton {
    background-color: #0070c0;
    color: #ffffff;
    border: none;
    border-radius: 5px;
    padding: 7px 16px;
    font-size: 13px;
    font-weight: 500;
}

QPushButton:hover {
    background-color: #005a9e;
}

QPushButton:pressed {
    background-color: #004480;
}

QPushButton:disabled {
    background-color: #2a3040;
    color: #4a5568;
}

QPushButton#secondary_btn {
    background-color: transparent;
    color: #3d9de8;
    border: 1px solid #3d9de8;
}

QPushButton#secondary_btn:hover {
    background-color: #1a3a5c;
}

QPushButton#danger_btn {
    background-color: #c0392b;
}

QPushButton#danger_btn:hover {
    background-color: #a93226;
}

QPushButton#success_btn {
    background-color: #1a7a4a;
}

QPushButton#success_btn:hover {
    background-color: #145e38;
}

/* ===== Tables ===== */
QTableWidget {
    background-color: #272c35;
    gridline-color: #343b47;
    border: 1px solid #343b47;
    border-radius: 6px;
    selection-background-color: #1a3a5c;
    selection-color: #e8ecf1;
}

QTableWidget::item {
    padding: 6px 8px;
    border-bottom: 1px solid #2a2f3a;
}

QTableWidget::item:selected {
    background-color: #1a3a5c;
    color: #e8ecf1;
}

QHeaderView::section {
    background-color: #22262e;
    color: #8a95a3;
    font-weight: bold;
    font-size: 12px;
    padding: 6px 8px;
    border: none;
    border-bottom: 2px solid #343b47;
}

/* ===== Scroll bars ===== */
QScrollBar:vertical {
    width: 10px;
    background: #1e2228;
    border-radius: 5px;
}

QScrollBar::handle:vertical {
    background: #3a4252;
    border-radius: 5px;
    min-height: 30px;
}

QScrollBar::handle:vertical:hover {
    background: #0070c0;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}

QScrollBar:horizontal {
    height: 10px;
    background: #1e2228;
    border-radius: 5px;
}

QScrollBar::handle:horizontal {
    background: #3a4252;
    border-radius: 5px;
    min-width: 30px;
}

QScrollBar::handle:horizontal:hover {
    background: #0070c0;
}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0px;
}

/* ===== Status bar ===== */
QStatusBar {
    background-color: #12151a;
    color: #6b7a8d;
    font-size: 12px;
    border-top: 1px solid #0d1014;
}

/* ===== Splitters ===== */
QSplitter::handle {
    background-color: #343b47;
}

QSplitter::handle:horizontal {
    width: 2px;
}

QSplitter::handle:vertical {
    height: 2px;
}

/* ===== Tab widget ===== */
QTabWidget::pane {
    border: none;
    background-color: #272c35;
    border-radius: 0px 8px 8px 8px;
}

QTabBar::tab {
    background-color: #22262e;
    color: #8a95a3;
    padding: 7px 18px;
    border-radius: 6px 6px 0px 0px;
    margin-right: 2px;
    font-size: 12px;
}

QTabBar::tab:selected {
    background-color: #272c35;
    color: #5aa8f0;
    font-weight: bold;
}

QTabBar::tab:hover:!selected {
    background-color: #2a2f3a;
}

/* ===== Progress bar ===== */
QProgressBar {
    background-color: #2a2f3a;
    border-radius: 4px;
    text-align: center;
    font-size: 11px;
    color: #e8ecf1;
    min-height: 16px;
    max-height: 16px;
}

QProgressBar::chunk {
    background-color: #0070c0;
    border-radius: 4px;
}

/* ===== Search bar ===== */
QLineEdit#search_bar {
    background-color: #2a2f3a;
    border: 2px solid #3d9de8;
    border-radius: 20px;
    padding: 8px 16px;
    font-size: 14px;
    color: #e8ecf1;
}

QLineEdit#search_bar:focus {
    border: 2px solid #5aa8f0;
}

/* ===== Tooltips ===== */
QToolTip {
    background-color: #12151a;
    color: #e8ecf1;
    border: 1px solid #343b47;
    padding: 4px 8px;
    border-radius: 4px;
    font-size: 12px;
}

/* ===== Message boxes ===== */
QMessageBox {
    background-color: #272c35;
}

/* ===== List widget ===== */
QListWidget {
    background-color: #272c35;
    border: 1px solid #343b47;
    border-radius: 6px;
    outline: none;
}

QListWidget::item {
    padding: 8px 12px;
    border-bottom: 1px solid #2a2f3a;
    color: #e8ecf1;
}

QListWidget::item:selected {
    background-color: #1a3a5c;
    color: #e8ecf1;
}

QListWidget::item:hover:!selected {
    background-color: #2a2f3a;
}

/* ===== Group boxes ===== */
QGroupBox {
    border: 1px solid #343b47;
    border-radius: 6px;
    margin-top: 12px;
    padding: 8px;
    font-weight: bold;
    color: #5aa8f0;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0px 8px;
    margin-left: 8px;
    color: #5aa8f0;
    font-size: 12px;
    font-weight: bold;
}

/* ===== Named structural widgets ===== */
QWidget#claim_list_sidebar {
    background-color: #1a1f26;
    border-right: 1px solid #343b47;
}

QWidget#table_header_row {
    background-color: #1a1f26;
    border-bottom: 2px solid #343b47;
}

QFrame#filter_bar, QWidget#filter_bar {
    background-color: #1a1f26;
    border-bottom: 1px solid #343b47;
}

QWidget#dialog_footer, QFrame#dialog_footer {
    background-color: #1a1f26;
    border-top: 1px solid #343b47;
}

QWidget#dialog_input_frame, QFrame#dialog_input_frame {
    background-color: #1a1f26;
    border-bottom: 1px solid #343b47;
}

QFrame#drop_zone {
    border: 2px dashed #3d9de8;
    background-color: #1a2a3a;
    border-radius: 8px;
}

QFrame#banner_success {
    background-color: #1a2e1f;
    border: 1px solid #2e7d32;
    border-radius: 8px;
}

QFrame#banner_success QLabel {
    color: #6fcf87;
    background: transparent;
}

QFrame#banner_warning {
    background-color: #2a2010;
    border: 1px solid #b8610a;
    border-radius: 8px;
}

QFrame#banner_warning QLabel {
    color: #f0b060;
    background: transparent;
}
"""


# ---------------------------------------------------------------------------
# Theme accessor
# ---------------------------------------------------------------------------

def get_style(dark: bool = False) -> str:
    """Return DARK_STYLE if dark=True, else MAIN_STYLE."""
    return DARK_STYLE if dark else MAIN_STYLE


# ---------------------------------------------------------------------------
# Color constants for Python-side use (QPainter, QColor, etc.)
# Light theme
# ---------------------------------------------------------------------------

COLOR_PRIMARY       = "#003366"
COLOR_ACCENT        = "#0070c0"
COLOR_ACCENT_LIGHT  = "#e3f0ff"
COLOR_SUCCESS       = "#1a7a4a"
COLOR_SUCCESS_LIGHT = "#e8f8f0"
COLOR_WARNING       = "#b8610a"
COLOR_WARNING_LIGHT = "#fff3e0"
COLOR_DANGER        = "#c0392b"
COLOR_DANGER_LIGHT  = "#fdecea"
COLOR_BG            = "#f0f2f5"
COLOR_CARD          = "#ffffff"
COLOR_BORDER        = "#dde2e8"
COLOR_TEXT          = "#1a1a2e"
COLOR_TEXT_MUTED    = "#555e6e"

# Dark theme equivalents
COLOR_DARK_BG       = "#1e2228"
COLOR_DARK_CARD     = "#272c35"
COLOR_DARK_BORDER   = "#343b47"
COLOR_DARK_TEXT     = "#e8ecf1"
COLOR_DARK_TEXT_MUTED = "#8a95a3"
COLOR_DARK_ACCENT   = "#3d9de8"
COLOR_DARK_PRIMARY  = "#5aa8f0"
