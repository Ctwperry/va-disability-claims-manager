"""
Qt background workers for long-running tasks (ingestion, search, export).
Uses QRunnable + QThreadPool to keep the UI responsive.
"""
import threading

from PyQt6.QtCore import QRunnable, QObject, pyqtSignal, pyqtSlot, QThreadPool
from app.db.connection import close_connection


class WorkerSignals(QObject):
    """Signals emitted by background workers."""
    progress = pyqtSignal(int, int, str)   # current, total, message
    result = pyqtSignal(object)            # any result object
    error = pyqtSignal(str)               # error message
    finished = pyqtSignal()


class IngestionWorker(QRunnable):
    """Runs the document ingestion pipeline in a thread pool."""

    def __init__(self, filepaths: list, veteran_id: int):
        super().__init__()
        self.filepaths = filepaths
        self.veteran_id = veteran_id
        self.signals = WorkerSignals()
        self.setAutoDelete(True)
        self._cancel_event = threading.Event()

    def cancel(self):
        """Signal the worker to stop after the current file completes."""
        self._cancel_event.set()

    @pyqtSlot()
    def run(self):
        try:
            from app.ingestion.pipeline import ingest_files

            def progress_cb(current, total, msg):
                self.signals.progress.emit(current, total, msg)

            results = ingest_files(
                self.filepaths,
                self.veteran_id,
                progress_cb=progress_cb,
                cancel_event=self._cancel_event,
            )
            self.signals.result.emit(results)
        except Exception as exc:
            import traceback
            self.signals.error.emit(traceback.format_exc())
        finally:
            close_connection()
            self.signals.finished.emit()


class SearchWorker(QRunnable):
    """Runs FTS5 search in a thread pool."""

    def __init__(self, query: str, veteran_id: int,
                 doc_type_filter: str = None, claim_id_filter: int = None):
        super().__init__()
        self.query = query
        self.veteran_id = veteran_id
        self.doc_type_filter = doc_type_filter
        self.claim_id_filter = claim_id_filter
        self.signals = WorkerSignals()
        self.setAutoDelete(True)

    @pyqtSlot()
    def run(self):
        try:
            from app.search.fts_engine import search
            results = search(
                self.query, self.veteran_id,
                doc_type_filter=self.doc_type_filter,
                claim_id_filter=self.claim_id_filter,
            )
            self.signals.result.emit(results)
        except Exception as exc:
            import traceback
            self.signals.error.emit(traceback.format_exc())
        finally:
            close_connection()
            self.signals.finished.emit()


_pool = None

def get_thread_pool() -> QThreadPool:
    global _pool
    if _pool is None:
        _pool = QThreadPool.globalInstance()
        _pool.setMaxThreadCount(4)
    return _pool
