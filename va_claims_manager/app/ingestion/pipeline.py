"""
Document ingestion pipeline.
Orchestrates: hash check → extraction → classification → DB insert.

Designed to run inside a QRunnable worker so the UI stays responsive.

Parallelism strategy
--------------------
Extraction (SHA-256 hash + PDF/DOCX/OCR text + classifier) is the slow part.
It runs in a ThreadPoolExecutor because:

  - pdfplumber, pytesseract, and docx parsing all release the GIL during the
    heavy work (C extensions, file I/O, subprocess calls to tesseract.exe), so
    Python threads get near-true concurrency without process-startup overhead.
  - Each thread opens its own file handle and its own pdfplumber context — no
    shared mutable state between workers.
  - pytesseract already calls tesseract.exe as a child process, so there is no
    Tesseract binary conflict between threads (each is a separate subprocess).

DB writes are serialised on the calling thread after extraction completes.
SQLite WAL mode allows concurrent reads, but we keep writes single-threaded to
avoid contention and simplify the deduplication check (hash_exists + create are
an atomic pair in a single thread).

Recommended `max_workers` = 4.  Beyond ~4–6 workers you hit diminishing returns
from disk I/O saturation and OCR memory pressure on typical hardware.
"""
from __future__ import annotations

import hashlib
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

log = logging.getLogger(__name__)

# Default parallel extraction worker count.
# Callers can override via the max_workers parameter.
MAX_EXTRACTION_WORKERS = 4

# Supported file extensions → internal type key
SUPPORTED_EXTENSIONS: dict[str, str] = {
    ".pdf":  "pdf",
    ".docx": "docx",
    ".doc":  "docx",
    ".jpg":  "image",
    ".jpeg": "image",
    ".png":  "image",
    ".tiff": "image",
    ".tif":  "image",
    ".bmp":  "image",
}


# ---------------------------------------------------------------------------
# Extraction result — data carrier between worker threads and the DB writer
# ---------------------------------------------------------------------------

@dataclass
class _ExtractionResult:
    """
    Holds everything produced by the worker thread for one file.
    The main thread reads this and performs all DB writes.
    """
    filepath: Path
    file_hash: str = ""
    file_type: str = ""
    pages: list[dict] = field(default_factory=list)
    ocr_used: bool = False
    doc_type: str = ""
    doc_date: str = ""
    author: str = ""
    facility: str = ""
    error: str = ""           # non-empty → extraction failed after hash
    pre_hash_error: str = ""  # non-empty → failed before / during hash
    is_unsupported: bool = False
    cancelled: bool = False   # True when ingest was cancelled before this file completed


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def ingest_files(
    filepaths: list[str | Path],
    veteran_id: int,
    progress_cb: Callable[[int, int, str], None] | None = None,
    max_workers: int = MAX_EXTRACTION_WORKERS,
    cancel_event=None,
) -> list[dict]:
    """
    Ingest a list of files for a given veteran.

    Extraction runs in parallel (ThreadPoolExecutor); DB writes are serialised
    on the calling thread.

    Args:
        filepaths:   Absolute paths to files to ingest.
        veteran_id:  The veteran these documents belong to.
        progress_cb: Optional callback(current, total, message) for progress.
        max_workers: Max parallel extraction threads (default 4).

    Returns:
        List of result dicts per file:
            {
              'filepath':   str,
              'filename':   str,
              'doc_id':     int,
              'status':     'success' | 'error' | 'duplicate',
              'doc_type':   str,
              'page_count': int,
              'message':    str,
            }
    """
    from app.db.repositories import document_repo
    from app.core.document import Document

    filepaths = [Path(fp) for fp in filepaths]
    total = len(filepaths)
    results: list[dict] = []
    completed = 0

    # ------------------------------------------------------------------
    # Phase 1 — parallel extraction
    # Submit all files immediately; collect results as they finish.
    # ------------------------------------------------------------------
    n_workers = max(1, min(max_workers, total))
    future_to_path: dict = {}

    with ThreadPoolExecutor(
        max_workers=n_workers,
        thread_name_prefix="ingest",
    ) as pool:
        for fp in filepaths:
            future_to_path[pool.submit(_extract_file, fp, cancel_event)] = fp

        for fut in as_completed(future_to_path):
            ext: _ExtractionResult = fut.result()   # never raises — worker catches all
            completed += 1
            _progress(progress_cb, completed, total, f"Processing: {ext.filepath.name}")

            # ---- Cancellation ----------------------------------------

            if ext.cancelled:
                results.append(_result(
                    ext.filepath, "cancelled",
                    message="Ingestion cancelled by user",
                ))
                continue

            # ---- Fast-path rejections --------------------------------

            if ext.is_unsupported:
                results.append(_result(
                    ext.filepath, "error",
                    message=f"Unsupported file type: {ext.filepath.suffix}",
                ))
                continue

            if ext.pre_hash_error:
                # Couldn't read the file at all — no DB record needed
                results.append(_result(ext.filepath, "error", message=ext.pre_hash_error))
                continue

            # ------------------------------------------------------------------
            # Phase 2 — DB writes (serialised here, one file at a time)
            # ------------------------------------------------------------------

            # Deduplication — runs after extraction so we don't delay the threads
            if document_repo.hash_exists(veteran_id, ext.file_hash):
                results.append(_result(
                    ext.filepath, "duplicate",
                    message="Already imported (duplicate)",
                ))
                continue

            if ext.error:
                # Extraction failed after we have the hash — persist the error record
                _record_error_doc(document_repo, Document, ext, veteran_id)
                results.append(_result(ext.filepath, "error", message=ext.error))
                continue

            # Happy path: create record → insert pages → update status + metadata
            doc = Document(
                veteran_id=veteran_id,
                filename=ext.filepath.name,
                filepath=str(ext.filepath),
                file_hash=ext.file_hash,
                file_size_bytes=ext.filepath.stat().st_size,
                ingestion_status="processing",
            )
            try:
                doc_id = document_repo.create(doc)
            except Exception as exc:
                log.exception("Failed to create DB record for %s", ext.filepath)
                results.append(_result(ext.filepath, "error",
                                       message=f"Database error: {exc}"))
                continue

            document_repo.insert_pages(doc_id, ext.pages)
            document_repo.update_status(
                doc_id, "complete",
                page_count=len(ext.pages),
                ocr_performed=ext.ocr_used,
            )
            document_repo.update_metadata(
                doc_id,
                doc_type=ext.doc_type,
                doc_date=ext.doc_date or None,
                author=ext.author or None,
                source_facility=ext.facility or None,
            )

            results.append(_result(
                ext.filepath, "success",
                doc_id=doc_id,
                doc_type=ext.doc_type,
                page_count=len(ext.pages),
                message=f"{len(ext.pages)} page(s), type: {ext.doc_type}",
            ))

    _progress(progress_cb, total, total, "Done")
    return results


# ---------------------------------------------------------------------------
# Worker — runs in a ThreadPoolExecutor thread
# ---------------------------------------------------------------------------

def _extract_file(filepath: Path, cancel_event=None) -> _ExtractionResult:
    """
    Extract text and metadata from one file.  Runs in a worker thread.

    Performs:
      1. File existence + extension check
      2. SHA-256 hash (dedup key)
      3. Text extraction (pdfplumber / docx / OCR)
      4. Classifier + date / author / facility hints

    Never raises — all exceptions are caught and stored in the result so the
    main thread can handle them without crashing the executor.
    """
    result = _ExtractionResult(filepath=filepath)

    # --- cancellation check (before any I/O) ---
    if cancel_event is not None and cancel_event.is_set():
        result.cancelled = True
        return result

    if not filepath.exists():
        result.pre_hash_error = "File not found"
        return result

    ext = filepath.suffix.lower()
    file_type = SUPPORTED_EXTENSIONS.get(ext)
    if not file_type:
        result.is_unsupported = True
        return result

    result.file_type = file_type

    # Step 1 — hash (fast I/O, but releases GIL for file reads)
    try:
        result.file_hash = _sha256(filepath)
    except Exception as exc:
        result.pre_hash_error = f"Cannot read file: {exc}"
        return result

    # --- cancellation check (after hash, before slow extraction) ---
    if cancel_event is not None and cancel_event.is_set():
        result.cancelled = True
        return result

    # Step 2 — extract pages
    try:
        pages, ocr_used = _extract(filepath, file_type)
        result.pages = pages
        result.ocr_used = ocr_used
    except Exception as exc:
        log.exception("Extraction failed for %s", filepath)
        result.error = str(exc)
        return result

    # Step 3 — classify (fast heuristic on first-page text)
    from app.ingestion.classifier import (
        classify, extract_date_hint, extract_author_hint, extract_facility_hint,
    )
    first_text = pages[0]["raw_text"] if pages else ""
    result.doc_type = classify(first_text)
    result.doc_date = extract_date_hint(first_text)
    result.author   = extract_author_hint(first_text)
    result.facility = extract_facility_hint(first_text)

    return result


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _extract(filepath: Path, file_type: str) -> tuple[list[dict], bool]:
    """
    Dispatch to the appropriate extractor.
    Returns (pages, ocr_was_used).
    pages = [{'page_number': n, 'raw_text': '...', 'has_image': bool}]
    """
    if file_type == "pdf":
        from app.ingestion.pdf_extractor import extract_pages
        pages = extract_pages(filepath, ocr_fallback=True)
        ocr_used = any(p.get("has_image") and len(p["raw_text"]) > 10 for p in pages)
        return pages, ocr_used

    elif file_type == "docx":
        from app.ingestion.docx_extractor import extract_pages
        return extract_pages(filepath), False

    elif file_type == "image":
        from app.ingestion.ocr_processor import ocr_image_file
        return ocr_image_file(filepath), True

    else:
        raise ValueError(f"Unknown file type: {file_type}")


def _sha256(filepath: Path) -> str:
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _record_error_doc(document_repo, Document, ext: _ExtractionResult, veteran_id: int):
    """Persist a minimal error record for a file that failed after hashing."""
    try:
        doc = Document(
            veteran_id=veteran_id,
            filename=ext.filepath.name,
            filepath=str(ext.filepath),
            file_hash=ext.file_hash,
            file_size_bytes=ext.filepath.stat().st_size,
            ingestion_status="error",
        )
        doc_id = document_repo.create(doc)
        document_repo.update_status(doc_id, "error", error=ext.error)
    except Exception:
        pass  # Best-effort; don't mask the original error


def _result(
    filepath: Path,
    status: str,
    doc_id: int = 0,
    doc_type: str = "",
    page_count: int = 0,
    message: str = "",
) -> dict:
    return {
        "filepath":   str(filepath),
        "filename":   filepath.name,
        "doc_id":     doc_id,
        "status":     status,
        "doc_type":   doc_type,
        "page_count": page_count,
        "message":    message,
    }


def _progress(cb: Callable | None, current: int, total: int, message: str):
    if cb:
        try:
            cb(current, total, message)
        except Exception:
            pass
