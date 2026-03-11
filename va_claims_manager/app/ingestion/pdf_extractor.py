"""
PDF text extraction using pdfplumber.
Falls back to OCR for image-based pages.
"""
import logging
from pathlib import Path

log = logging.getLogger(__name__)


def extract_pages(filepath: str | Path, ocr_fallback: bool = True) -> list[dict]:
    """
    Extract text from each page of a PDF.

    Returns a list of dicts:
        [{'page_number': 1, 'raw_text': '...', 'has_image': True/False}, ...]
    """
    import pdfplumber
    from app.config import OCR_FALLBACK_THRESHOLD

    pages = []
    try:
        with pdfplumber.open(str(filepath)) as pdf:
            for i, page in enumerate(pdf.pages, start=1):
                text = page.extract_text() or ""
                has_image = bool(page.images)

                if len(text.strip()) < OCR_FALLBACK_THRESHOLD and ocr_fallback:
                    # Image-based page — try OCR
                    log.debug("Page %d: text too short (%d chars), trying OCR", i, len(text))
                    ocr_text = _ocr_pdf_page(page)
                    if ocr_text:
                        text = ocr_text
                        has_image = True

                pages.append({
                    "page_number": i,
                    "raw_text": text,
                    "has_image": has_image,
                })
    except Exception as exc:
        log.error("Failed to extract PDF %s: %s", filepath, exc)
        raise

    return pages


def _ocr_pdf_page(page) -> str:
    """Render a pdfplumber page to an image and OCR it."""
    try:
        from app.ingestion.ocr_processor import ocr_pil_image
        # Render at 200 DPI for good OCR quality
        img = page.to_image(resolution=200).original
        return ocr_pil_image(img)
    except Exception as exc:
        log.warning("OCR fallback failed: %s", exc)
        return ""
