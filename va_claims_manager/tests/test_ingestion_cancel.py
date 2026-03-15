"""
Tests for user-initiated cancellation of the ingestion pipeline.

ingest_files() accepts an optional threading.Event cancel_event.
When it is set before or during ingestion, files not yet committed
to the DB are returned with status="cancelled".

These tests use non-existent paths deliberately — the cancel check
fires before the filepath.exists() check, so no real files are needed.
"""
import threading


def test_cancel_before_start_marks_all_files_cancelled():
    """Pre-setting the event before ingest_files() starts marks every file cancelled."""
    from app.ingestion.pipeline import ingest_files

    cancel = threading.Event()
    cancel.set()

    results = ingest_files(
        ["/nonexistent/a.pdf", "/nonexistent/b.pdf", "/nonexistent/c.pdf"],
        veteran_id=1,
        cancel_event=cancel,
    )

    assert len(results) == 3
    assert all(r["status"] == "cancelled" for r in results)


def test_cancel_result_contains_filename():
    """Cancelled results still report the original filename."""
    from app.ingestion.pipeline import ingest_files

    cancel = threading.Event()
    cancel.set()

    results = ingest_files(["/nonexistent/my_document.pdf"], veteran_id=1, cancel_event=cancel)

    assert results[0]["filename"] == "my_document.pdf"
    assert results[0]["status"] == "cancelled"


def test_no_cancel_event_behaves_normally():
    """Passing cancel_event=None must not change existing behaviour."""
    from app.ingestion.pipeline import ingest_files

    # Non-existent file with no cancel_event → error, not cancelled
    results = ingest_files(["/nonexistent/x.pdf"], veteran_id=1, cancel_event=None)

    assert results[0]["status"] == "error"
    assert results[0]["status"] != "cancelled"


def test_ingestion_worker_has_cancel_method():
    """IngestionWorker must expose a cancel() method."""
    from app.ui.workers import IngestionWorker

    worker = IngestionWorker(["/fake.pdf"], veteran_id=1)
    assert callable(getattr(worker, "cancel", None))


def test_ingestion_worker_cancel_is_idempotent():
    """Calling cancel() multiple times must not raise."""
    from app.ui.workers import IngestionWorker

    worker = IngestionWorker(["/fake.pdf"], veteran_id=1)
    worker.cancel()
    worker.cancel()  # second call must not raise
