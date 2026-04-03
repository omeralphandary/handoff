"""Tests for InspectionTask.

Covers: baseline establishment, diff threshold, VLM gating, flagging,
baseline update on clean pass, and reset.
"""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
import numpy as np
from unittest.mock import AsyncMock, MagicMock, patch


def _blank(value: int = 0) -> np.ndarray:
    """Solid-colour 200x200 BGR frame."""
    frame = np.full((200, 200, 3), value, dtype=np.uint8)
    return frame


def _make_zone(zone_id: str = "zone-1") -> MagicMock:
    z = MagicMock()
    z.id = zone_id
    z.name = "Test Zone"
    z.retention_days = 90
    return z


def _make_task(tmp_path: Path, vlm_result: dict):
    from tasks.inspection import InspectionTask

    mock_vlm = AsyncMock()
    mock_vlm.analyze = AsyncMock(return_value=vlm_result)

    mock_store = AsyncMock()
    mock_store.save = AsyncMock(return_value={"id": "rec-1"})

    with patch("tasks.inspection._BASELINES_DIR", tmp_path):
        task = InspectionTask(vlm=mock_vlm, store=mock_store)
        task.__baselines_dir = tmp_path  # keep reference for assertions
    return task, mock_vlm, mock_store


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_first_frame_sets_baseline_no_save(tmp_path):
    """First run establishes baseline; nothing saved to store."""
    task, mock_vlm, mock_store = _make_task(tmp_path, vlm_result={})

    with patch("tasks.inspection._BASELINES_DIR", tmp_path):
        await task.run(_blank(0), _make_zone())

    mock_vlm.analyze.assert_not_called()
    mock_store.save.assert_not_called()
    assert (tmp_path / "zone-1.jpg").exists()


@pytest.mark.asyncio
async def test_identical_frame_skips_vlm(tmp_path):
    """Identical frame (diff=0%) does not call VLM."""
    task, mock_vlm, mock_store = _make_task(tmp_path, vlm_result={})
    zone = _make_zone()
    frame = _blank(50)

    with patch("tasks.inspection._BASELINES_DIR", tmp_path):
        await task.run(frame, zone)          # sets baseline
        await task.run(frame.copy(), zone)   # identical → skip

    mock_vlm.analyze.assert_not_called()
    mock_store.save.assert_not_called()


@pytest.mark.asyncio
async def test_changed_frame_triggers_vlm(tmp_path):
    """Frame significantly different from baseline triggers VLM."""
    vlm_result = {
        "anomaly_detected": True,
        "anomalies": [{"description": "object moved", "severity": "medium", "location": "center"}],
        "summary": "Pallet shifted.",
    }
    task, mock_vlm, mock_store = _make_task(tmp_path, vlm_result=vlm_result)
    zone = _make_zone()

    with patch("tasks.inspection._BASELINES_DIR", tmp_path):
        await task.run(_blank(0), zone)       # baseline
        await task.run(_blank(200), zone)     # very different

    mock_vlm.analyze.assert_called_once()
    mock_store.save.assert_called_once()


@pytest.mark.asyncio
async def test_anomaly_detected_is_flagged(tmp_path):
    """anomaly_detected=True from VLM → flagged=True in saved result."""
    vlm_result = {
        "anomaly_detected": True,
        "anomalies": [{"description": "spill", "severity": "high", "location": "floor"}],
        "summary": "Hazard detected.",
    }
    task, mock_vlm, mock_store = _make_task(tmp_path, vlm_result=vlm_result)
    zone = _make_zone()

    with patch("tasks.inspection._BASELINES_DIR", tmp_path):
        await task.run(_blank(0), zone)
        await task.run(_blank(200), zone)

    saved_result = mock_store.save.call_args.kwargs["result"]
    assert saved_result["flagged"] is True
    assert "baseline_diff_pct" in saved_result


@pytest.mark.asyncio
async def test_clean_pass_updates_baseline(tmp_path):
    """If VLM returns no anomaly, baseline updates to new frame."""
    import cv2
    vlm_result = {
        "anomaly_detected": False,
        "anomalies": [],
        "summary": "Scene normal.",
    }
    task, mock_vlm, mock_store = _make_task(tmp_path, vlm_result=vlm_result)
    zone = _make_zone()
    new_frame = _blank(200)

    with patch("tasks.inspection._BASELINES_DIR", tmp_path):
        await task.run(_blank(0), zone)     # baseline = black
        await task.run(new_frame, zone)     # big diff, no anomaly → update

    # Baseline should now be the new (white-ish) frame
    saved_baseline = cv2.imread(str(tmp_path / "zone-1.jpg"))
    assert saved_baseline is not None
    assert saved_baseline.mean() > 100  # was 0 before


@pytest.mark.asyncio
async def test_parse_error_flagged(tmp_path):
    """VLM parse failure → flagged=True."""
    task, mock_vlm, mock_store = _make_task(
        tmp_path, vlm_result={"raw": "oops", "parse_error": True}
    )
    zone = _make_zone()

    with patch("tasks.inspection._BASELINES_DIR", tmp_path):
        await task.run(_blank(0), zone)
        await task.run(_blank(200), zone)

    saved_result = mock_store.save.call_args.kwargs["result"]
    assert saved_result["flagged"] is True


@pytest.mark.asyncio
async def test_reset_baseline_removes_file(tmp_path):
    """reset_baseline() deletes the stored baseline file."""
    task, _, __ = _make_task(tmp_path, vlm_result={})
    zone = _make_zone()

    with patch("tasks.inspection._BASELINES_DIR", tmp_path):
        await task.run(_blank(0), zone)
        assert (tmp_path / "zone-1.jpg").exists()
        task.reset_baseline(zone)
        assert not (tmp_path / "zone-1.jpg").exists()


@pytest.mark.asyncio
async def test_task_type_is_inspection(tmp_path):
    """Saved record must have task_type='inspection'."""
    vlm_result = {"anomaly_detected": False, "anomalies": [], "summary": "ok"}
    task, _, mock_store = _make_task(tmp_path, vlm_result=vlm_result)
    zone = _make_zone()

    with patch("tasks.inspection._BASELINES_DIR", tmp_path):
        await task.run(_blank(0), zone)
        await task.run(_blank(200), zone)

    assert mock_store.save.call_args.kwargs["task_type"] == "inspection"
