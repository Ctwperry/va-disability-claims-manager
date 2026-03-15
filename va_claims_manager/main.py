"""
VA Disability Claims Manager — Entry Point
Run: python main.py
"""
import sys
import os
import logging

# Ensure the project root is on sys.path when run directly
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt6.QtWidgets import QApplication, QSplashScreen, QMessageBox
from PyQt6.QtGui import QPixmap, QColor, QPainter, QFont
from PyQt6.QtCore import Qt, QTimer

from app.config import APP_NAME, APP_VERSION, DB_PATH
from app.db.encryption import ensure_key, is_plaintext_db, migrate_plaintext_to_encrypted
from app.db.schema import initialize_database
from app.ui.app_window import MainWindow

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger(__name__)


def create_splash() -> QSplashScreen:
    """Create a simple programmatic splash screen."""
    pixmap = QPixmap(520, 200)
    pixmap.fill(QColor("#003366"))

    painter = QPainter(pixmap)
    painter.setPen(QColor("#ffffff"))

    title_font = QFont("Segoe UI", 22, QFont.Weight.Bold)
    painter.setFont(title_font)
    painter.drawText(30, 70, APP_NAME)

    sub_font = QFont("Segoe UI", 12)
    painter.setFont(sub_font)
    painter.setPen(QColor("#a0bdd8"))
    painter.drawText(30, 100, f"Version {APP_VERSION}")
    painter.drawText(30, 130, "Loading application...")

    accent_font = QFont("Segoe UI", 10, QFont.Weight.Bold)
    painter.setFont(accent_font)
    painter.setPen(QColor("#66b2ff"))
    painter.drawText(30, 170, "Supporting Veterans' Claims")
    painter.end()

    splash = QSplashScreen(pixmap)
    splash.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint)
    return splash


def main():
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)
    app.setOrganizationName("VA Claims Tools")

    # Show splash
    splash = create_splash()
    splash.show()
    app.processEvents()

    # Initialize encryption key + database
    try:
        splash.showMessage(
            "  Initializing encryption...",
            Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignLeft,
            QColor("#a0bdd8"),
        )
        app.processEvents()

        # Retrieve (or generate on first launch) the encryption key
        key = ensure_key()
        log.info("Encryption key ready")

        # Migrate existing plaintext database if one exists
        if DB_PATH.exists() and is_plaintext_db(DB_PATH):
            splash.showMessage(
                "  Encrypting existing database...",
                Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignLeft,
                QColor("#a0bdd8"),
            )
            app.processEvents()
            backup = migrate_plaintext_to_encrypted(DB_PATH, key)
            log.info("Plaintext DB migrated; backup at %s", backup)

        splash.showMessage(
            "  Initializing database...",
            Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignLeft,
            QColor("#a0bdd8"),
        )
        app.processEvents()
        initialize_database()
        log.info("Database ready: %s", DB_PATH)
    except Exception as exc:
        splash.hide()
        QMessageBox.critical(
            None, "Startup Error",
            f"Failed to initialize database:\n{exc}\n\n"
            f"Database path: {DB_PATH}"
        )
        sys.exit(1)

    # Launch main window
    splash.showMessage(
        "  Starting application...",
        Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignLeft,
        QColor("#a0bdd8"),
    )
    app.processEvents()

    window = MainWindow()
    window.show()

    # Close splash after window is visible
    QTimer.singleShot(400, splash.close)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
