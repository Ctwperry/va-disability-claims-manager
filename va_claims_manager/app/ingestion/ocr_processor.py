"""
OCR processing using pytesseract with OpenCV preprocessing.
"""
import logging
from pathlib import Path

log = logging.getLogger(__name__)

_tesseract_configured = False


def _ensure_tesseract():
    global _tesseract_configured
    if _tesseract_configured:
        return
    import pytesseract
    from app.db.schema import get_setting
    from app.config import TESSERACT_DEFAULT_PATHS

    saved_path = get_setting("tesseract_path", "")
    if saved_path and Path(saved_path).exists():
        pytesseract.pytesseract.tesseract_cmd = saved_path
        _tesseract_configured = True
        return

    for path in TESSERACT_DEFAULT_PATHS:
        if Path(path).exists():
            pytesseract.pytesseract.tesseract_cmd = path
            _tesseract_configured = True
            log.info("Tesseract found at: %s", path)
            return

    log.warning("Tesseract not found at any default path. OCR will be unavailable.")
    _tesseract_configured = True  # Mark as checked so we don't retry every time


def ocr_pil_image(img) -> str:
    """
    OCR a PIL Image. Applies OpenCV preprocessing to improve accuracy.
    Returns extracted text string.
    """
    _ensure_tesseract()
    try:
        import pytesseract
        preprocessed = _preprocess(img)
        text = pytesseract.image_to_string(preprocessed, config="--oem 3 --psm 6")
        return text
    except Exception as exc:
        log.warning("OCR failed: %s", exc)
        return ""


def ocr_image_file(filepath: str | Path) -> list[dict]:
    """
    OCR a standalone image file (JPEG, PNG, TIFF, BMP).
    Returns a single-element list: [{'page_number': 1, 'raw_text': '...', 'has_image': True}]
    """
    from PIL import Image
    try:
        img = Image.open(str(filepath))
        text = ocr_pil_image(img)
        return [{"page_number": 1, "raw_text": text, "has_image": True}]
    except Exception as exc:
        log.error("Failed to OCR image %s: %s", filepath, exc)
        raise


def _preprocess(pil_img):
    """
    Apply OpenCV preprocessing to a PIL image for better OCR accuracy:
    1. Convert to grayscale
    2. Deskew
    3. Adaptive threshold (binarize)
    Returns a PIL image.
    """
    try:
        import cv2
        import numpy as np
        from PIL import Image

        img_array = np.array(pil_img.convert("RGB"))
        gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)

        # Deskew
        gray = _deskew(gray)

        # Adaptive threshold
        binary = cv2.adaptiveThreshold(
            gray, 255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            31, 11,
        )

        return Image.fromarray(binary)
    except Exception as exc:
        log.debug("Preprocessing failed (%s), using original image", exc)
        return pil_img


def _deskew(gray_array):
    """Deskew a grayscale numpy array."""
    try:
        import cv2
        import numpy as np
        coords = np.column_stack(np.where(gray_array < 128))
        if len(coords) < 50:
            return gray_array
        angle = cv2.minAreaRect(coords)[-1]
        if angle < -45:
            angle = -(90 + angle)
        else:
            angle = -angle
        if abs(angle) < 0.5:
            return gray_array
        (h, w) = gray_array.shape
        center = (w // 2, h // 2)
        M = cv2.getRotationMatrix2D(center, angle, 1.0)
        rotated = cv2.warpAffine(
            gray_array, M, (w, h),
            flags=cv2.INTER_CUBIC,
            borderMode=cv2.BORDER_REPLICATE,
        )
        return rotated
    except Exception:
        return gray_array
