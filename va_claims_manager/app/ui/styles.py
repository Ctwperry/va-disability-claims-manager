"""
Application-wide QSS stylesheet — professional light theme with VA blue accents.
"""

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
"""

# Color constants for Python-side use (QPainter, etc.)
COLOR_PRIMARY = "#003366"
COLOR_ACCENT = "#0070c0"
COLOR_ACCENT_LIGHT = "#e3f0ff"
COLOR_SUCCESS = "#1a7a4a"
COLOR_SUCCESS_LIGHT = "#e8f8f0"
COLOR_WARNING = "#b8610a"
COLOR_WARNING_LIGHT = "#fff3e0"
COLOR_DANGER = "#c0392b"
COLOR_DANGER_LIGHT = "#fdecea"
COLOR_BG = "#f0f2f5"
COLOR_CARD = "#ffffff"
COLOR_BORDER = "#dde2e8"
COLOR_TEXT = "#1a1a2e"
COLOR_TEXT_MUTED = "#555e6e"
