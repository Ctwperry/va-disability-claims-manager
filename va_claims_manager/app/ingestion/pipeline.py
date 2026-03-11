"""
Document ingestion pipeline.
Orchestrates: hash check → extraction → classification → DB insert.

Designed to run inside a QRunnable worker so the UI stays responsive.
The pipeline emits progress via a callback function rather than Qt signals
(so it can also be used in tests without a QApplication).
"""
import hashlib
import logging
import os
from pathlib import Path
from typing import Callable

log = logging.getLogger(__name__)

# Supported file types
SUPPORTED_EXTENSIONS = {
    ".pdf": "pdf",
    ".docx": "docx",
    ".doc": "docx",
    ".jpg": "image",
    ".jpeg": "image",
    ".png": "image",
    ".tiff": "image",
    ".tif": "image",
    ".bmp": "image",
}


def ingest_files(
    filepaths: list[str | Path],
    veteran_id: int,
    progress_cb: Callable[[int, int, str], None] | None = None,
) -> list[dict]:
    """
    Ingest a list of files for a given veteran.

    Args:
        filepaths: Absolute paths to files to ingest.
        veteran_id: The veteran these documents belong to.
        progress_cb: Optional callback(current, total, message) for progress updates.

    Returns:
        List of result dicts:
            {'filepath': str, 'doc_id': int, 'status': 'success'|'error'|'duplicate',
             'doc_type': str, 'page_count': int, 'message': str}
    """
    from app.db.repositories import document_repo
    from app.core.document import Document

    results = []
    total = len(filepaths)

    for idx, filepath in enumerate(filepaths):
        filepath = Path(filepath)
        _progress(progress_cb, idx, total, f"Processing: {filepath.name}")

        if not filepath.exists():
            results.append(_result(filepath, "error", message="File not found"))
            continue

        ext = filepath.suffix.lower()
        file_type = SUPPORTED_EXTENSIONS.get(ext)
        if not file_type:
            results.append(_result(filepath, "error", message=f"Unsupported file type: {ext}"))
            continue

        # Hash for deduplication
        try:
            file_hash = _sha256(filepath)
        except Exception as exc:
            results.append(_result(filepath, "error", message=f"Cannot read file: {exc}"))
            continue

        if document_repo.hash_exists(veteran_id, file_hash):
            results.append(_result(filepath, "duplicate", message="Already imported (duplicate)"))
            continue

        # Create document record
        file_size = filepath.stat().st_size
        doc = Document(
            veteran_id=veteran_id,
            filename=filepath.name,
            filepath=str(filepath),
            file_hash=file_hash,
            file_size_bytes=file_size,
            ingestion_status="processing",
        )
        try:
            doc_id = document_repo.create(doc)
        except Exception as exc:
            log.exception("Failed to create DB record for %s", filepath)
            results.append(_result(filepath, "error", message=f"Database error: {exc}"))
            continue

        # Extract pages
        try:
            pages, ocr_used = _extract(filepath, file_type)
        except Exception as exc:
            log.exception("Extraction failed for %s", filepath)
            document_repo.update_status(doc_id, "error", error=str(exc))
            results.append(_result(filepath, "error", message=str(exc), doc_id=doc_id))
            continue

        # Classify document type from first page text
        first_text = pages[0]["raw_text"] if pages else ""
        from app.ingestion.classifier import classify, extract_date_hint, extract_author_hint, extract_facility_hint
        doc_type = classify(first_text)
        doc_date = extract_date_hint(first_text)
        author = extract_author_hint(first_text)
        facility = extract_facility_hint(first_text)

        # Store pages in DB (FTS5 triggers fire automatically)
        document_repo.insert_pages(doc_id, pages)

        # Update document status and metadata
        document_repo.update_status(
            doc_id, "complete",
            page_count=len(pages),
            ocr_performed=ocr_used,
        )
        document_repo.update_metadata(
            doc_id,
            doc_type=doc_type,
            doc_date=doc_date or None,
            author=author or None,
            source_facility=facility or None,
        )

        results.append(_result(
            filepath, "success",
            doc_id=doc_id,
            doc_type=doc_type,
            page_count=len(pages),
            message=f"{len(pages)} page(s), type: {doc_type}",
        ))

    _progress(progress_cb, total, total, "Done")
    return results


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _extract(filepath: Path, file_type: str) -> tuple[list[dict], bool]:
    """
    Return (pages, ocr_was_used).
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


def _result(filepath: Path, status: str, doc_id: int = 0,
            doc_type: str = "", page_count: int = 0, message: str = "") -> dict:
    return {
        "filepath": str(filepath),
        "filename": filepath.name,
        "doc_id": doc_id,
        "status": status,
        "doc_type": doc_type,
        "page_count": page_count,
        "message": message,
    }


def _progress(cb, current: int, total: int, message: str):
    if cb:
        try:
            cb(current, total, message)
        except Exception:
            pass
