"""Low-level OCR helpers — pyzbar + EasyOCR.

Isolated here so they can be mocked cleanly in tests without
importing heavy deps in every test file.
"""
from __future__ import annotations
import cv2
import numpy as np


def sharpen(frame: np.ndarray) -> np.ndarray:
    """Unsharp mask — enhances edges to compensate for soft-focus blur."""
    blurred = cv2.GaussianBlur(frame, (0, 0), 3)
    return cv2.addWeighted(frame, 1.5, blurred, -0.5, 0)


def read_barcodes(frame: np.ndarray) -> list[str]:
    """Decode barcodes and QR codes.

    Tries pyzbar first (requires libzbar0 system lib), falls back to
    OpenCV's built-in QR detector. Returns empty list on any failure.
    """
    frame = sharpen(frame)
    results: list[str] = []

    # pyzbar — richest support, needs libzbar0 installed
    try:
        from pyzbar.pyzbar import decode as pyzbar_decode
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        for d in pyzbar_decode(gray):
            val = d.data.decode("utf-8", errors="replace").strip()
            if val:
                results.append(val)
        if results:
            return results
    except Exception:
        pass

    # cv2 QR fallback (no system dep, lower decode rate on distorted images)
    try:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        qr = cv2.QRCodeDetector()
        data, bbox, _ = qr.detectAndDecode(gray)
        if data:
            results.append(data)
    except Exception:
        pass

    return results


# Module-level reader singleton — EasyOCR loads a model on first call (~2s).
_easyocr_reader = None


def read_text(frame: np.ndarray) -> list[str]:
    """Extract text with EasyOCR. Returns list of detected strings."""
    global _easyocr_reader
    try:
        import easyocr
        if _easyocr_reader is None:
            _easyocr_reader = easyocr.Reader(["en"], gpu=True, verbose=False)
        results = _easyocr_reader.readtext(sharpen(frame), detail=0, paragraph=False)
        return [str(r).strip() for r in results if str(r).strip()]
    except Exception as e:
        import logging
        logging.getLogger(__name__).error("[ocr] EasyOCR failed: %s", e, exc_info=True)
        return []
