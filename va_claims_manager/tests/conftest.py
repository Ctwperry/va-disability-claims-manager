"""
Shared pytest fixtures and setup.

- Stubs PyQt6 so app.ui.* modules can be imported without a display server.
- Redirects DB connections to a per-test temp database.
"""
import sys
from unittest.mock import MagicMock
import pytest

# ---------------------------------------------------------------------------
# Stub PyQt6 at import time so tests can import app.ui.* without Qt installed.
#
# QObject and QRunnable must be real Python types (not MagicMock instances).
# If they're left as mocks, Python's __mro_entries__ protocol turns any class
# that inherits from them into a MagicMock, clobbering all method definitions.
#
# pyqtSlot and pyqtSignal must be no-op pass-throughs, not raw MagicMocks.
# If left as MagicMocks, @pyqtSlot() replaces decorated methods with a
# MagicMock return value, silently hiding the real implementation.
# ---------------------------------------------------------------------------
class _QObject:
    pass


class _QRunnable:
    def setAutoDelete(self, val):
        pass


def _noop_decorator(*args, **kwargs):
    """Identity decorator — returns the decorated callable unchanged."""
    def decorator(fn):
        return fn
    return decorator


_qt_core_mock = MagicMock()
_qt_core_mock.QObject = _QObject
_qt_core_mock.QRunnable = _QRunnable
_qt_core_mock.pyqtSlot = _noop_decorator
# pyqtSignal must return a MagicMock (not a plain function) so that
# class-level signal attributes have an .emit() method callable in tests.
_qt_core_mock.pyqtSignal = lambda *a, **kw: MagicMock()

for _mod, _stub in [
    ("PyQt6", MagicMock()),
    ("PyQt6.QtCore", _qt_core_mock),
    ("PyQt6.QtWidgets", MagicMock()),
    ("PyQt6.QtGui", MagicMock()),
]:
    if _mod not in sys.modules:
        sys.modules[_mod] = _stub


# ---------------------------------------------------------------------------
# Per-test isolated SQLite database — never touches the production DB.
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def use_temp_db(tmp_path, monkeypatch):
    import app.db.connection as conn_mod

    monkeypatch.setattr(conn_mod, "DB_PATH", tmp_path / "test.db")
    conn_mod.close_connection()  # clear any leftover thread-local conn
    yield
    conn_mod.close_connection()  # clean up after test
