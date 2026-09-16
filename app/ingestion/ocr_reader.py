"""
OCR via Tesseract (optional).

If pytesseract or the tesseract binary isn't installed,
the module fails gracefully and returns an empty result.

Install on Termux:
    pkg install tesseract tesseract-lang -y
    pip install pytesseract
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class OCRResult:
    text: str = ""
    lang: str | None = None
    available: bool = False
    error: str | None = None


def is_ocr_available() -> bool:
    """Return True if pytesseract + Pillow are importable."""
    try:
        import pytesseract  # noqa: F401
        from PIL import Image  # noqa: F401
        return True
    except Exception:
        return False


def read_image(path: str | Path, lang: str = "eng+mya") -> OCRResult:
    """
    Extract text from an image file.

    Best-effort: returns available=False if OCR stack is missing.
    """
    if not is_ocr_available():
        return OCRResult(
            available=False,
            error="pytesseract or Pillow not installed",
        )

    try:
        import pytesseract
        from PIL import Image
    except Exception as e:
        return OCRResult(available=False, error=str(e))

    try:
        with Image.open(path) as img:
            # Light preprocessing helps
            if img.mode != "RGB":
                img = img.convert("RGB")
            try:
                text = pytesseract.image_to_string(img, lang=lang)
            except Exception:
                # Fallback to English if Myanmar language pack is missing
                text = pytesseract.image_to_string(img, lang="eng")
        return OCRResult(text=(text or "").strip(), lang=lang, available=True)
    except Exception as e:
        return OCRResult(available=True, error=str(e))
