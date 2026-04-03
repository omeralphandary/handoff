"""Tests for OCRTask.

All external deps (VLM client, store, OCR readers) are mocked — no GPU,
no network, no DB required.
"""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
import numpy as np
from unittest.mock import AsyncMock, MagicMock, patch


def _make_frame() -> np.ndarray:
    """Blank 640x480 BGR frame."""
    return np.zeros((480, 640, 3), dtype=np.uint8)


def _make_zone(zone_id: str = "zone-1") -> MagicMock:
    z = MagicMock()
    z.id = zone_id
    z.name = "Test Zone"
    z.retention_days = 90
    return z


# ---------------------------------------------------------------------------
# Helpers to reduce boilerplate
# ---------------------------------------------------------------------------

def _make_task(vlm_result: dict, barcodes: list[str], texts: list[str]):
    """Return (task, mock_store) with patched readers and VLM."""
    from tasks.ocr import OCRTask

    mock_vlm = AsyncMock()
    mock_vlm.analyze = AsyncMock(return_value=vlm_result)

    mock_store = AsyncMock()
    mock_store.save = AsyncMock(return_value={"id": "rec-1"})

    task = OCRTask(vlm=mock_vlm, store=mock_store)
    return task, mock_vlm, mock_store, barcodes, texts


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_ocr_calls_vlm_when_text_found():
    """When OCR reads text, VLM should be called for cleanup."""
    vlm_result = {
        "texts": ["TRACK-1234"],
        "barcodes": [],
        "identifiers": [{"label": "Tracking", "value": "TRACK-1234"}],
        "summary": "Tracking label found.",
        "flagged": False,
    }
    task, mock_vlm, mock_store, barcodes, texts = _make_task(
        vlm_result, barcodes=[], texts=["TRACK-1234"]
    )

    with patch("tasks.ocr.read_barcodes", return_value=barcodes), \
         patch("tasks.ocr.read_text", return_value=texts):
        await task.run(_make_frame(), _make_zone())

    mock_vlm.analyze.assert_called_once()
    mock_store.save.assert_called_once()
    saved_result = mock_store.save.call_args.kwargs["result"]
    assert saved_result["flagged"] is False
    assert saved_result["identifiers"][0]["value"] == "TRACK-1234"


@pytest.mark.asyncio
async def test_ocr_calls_vlm_when_barcode_found():
    """Barcodes without text should still trigger VLM."""
    vlm_result = {
        "texts": [],
        "barcodes": ["ABC-9999"],
        "identifiers": [{"label": "Barcode", "value": "ABC-9999"}],
        "summary": "Barcode scanned.",
        "flagged": False,
    }
    task, mock_vlm, mock_store, barcodes, texts = _make_task(
        vlm_result, barcodes=["ABC-9999"], texts=[]
    )

    with patch("tasks.ocr.read_barcodes", return_value=barcodes), \
         patch("tasks.ocr.read_text", return_value=texts):
        await task.run(_make_frame(), _make_zone())

    mock_vlm.analyze.assert_called_once()
    saved_result = mock_store.save.call_args.kwargs["result"]
    assert saved_result["flagged"] is False


@pytest.mark.asyncio
async def test_ocr_flagged_when_nothing_read():
    """Empty reads → skip VLM, save flagged=True immediately."""
    task, mock_vlm, mock_store, _, __ = _make_task(
        vlm_result={}, barcodes=[], texts=[]
    )

    with patch("tasks.ocr.read_barcodes", return_value=[]), \
         patch("tasks.ocr.read_text", return_value=[]):
        await task.run(_make_frame(), _make_zone())

    mock_vlm.analyze.assert_not_called()
    mock_store.save.assert_called_once()
    saved_result = mock_store.save.call_args.kwargs["result"]
    assert saved_result["flagged"] is True


@pytest.mark.asyncio
async def test_ocr_flagged_on_vlm_parse_error():
    """VLM parse failure → flagged=True, raw reads preserved."""
    task, mock_vlm, mock_store, barcodes, texts = _make_task(
        vlm_result={"raw": "sorry, no json here", "parse_error": True},
        barcodes=["QR-XYZ"],
        texts=["SHIP-001"],
    )

    with patch("tasks.ocr.read_barcodes", return_value=barcodes), \
         patch("tasks.ocr.read_text", return_value=texts):
        await task.run(_make_frame(), _make_zone())

    saved_result = mock_store.save.call_args.kwargs["result"]
    assert saved_result["flagged"] is True
    # Raw reads must be preserved so the record isn't empty
    assert "QR-XYZ" in saved_result["barcodes"]
    assert "SHIP-001" in saved_result["texts"]


@pytest.mark.asyncio
async def test_ocr_vlm_can_override_flagged_true():
    """VLM may return flagged=True even when reads succeeded (nothing meaningful)."""
    vlm_result = {
        "texts": ["..."],
        "barcodes": [],
        "identifiers": [],
        "summary": "Unreadable label.",
        "flagged": True,
    }
    task, mock_vlm, mock_store, barcodes, texts = _make_task(
        vlm_result, barcodes=[], texts=["..."]
    )

    with patch("tasks.ocr.read_barcodes", return_value=barcodes), \
         patch("tasks.ocr.read_text", return_value=texts):
        await task.run(_make_frame(), _make_zone())

    saved_result = mock_store.save.call_args.kwargs["result"]
    assert saved_result["flagged"] is True


@pytest.mark.asyncio
async def test_ocr_task_type_is_ocr():
    """Saved record must have task_type='ocr'."""
    vlm_result = {"texts": ["X"], "barcodes": [], "identifiers": [], "summary": "ok", "flagged": False}
    task, _, mock_store, _, __ = _make_task(vlm_result, barcodes=[], texts=["X"])

    with patch("tasks.ocr.read_barcodes", return_value=[]), \
         patch("tasks.ocr.read_text", return_value=["X"]):
        await task.run(_make_frame(), _make_zone())

    assert mock_store.save.call_args.kwargs["task_type"] == "ocr"
