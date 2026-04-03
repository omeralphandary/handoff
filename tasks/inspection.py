"""Continuous inspection task — anomaly detection against a baseline frame.

Pipeline:
  1. First frame sets the baseline (saved to disk per zone, persists across restarts).
  2. Subsequent frames are pixel-diffed against baseline.
  3. Only if diff exceeds threshold is the VLM called — avoids unnecessary API spend.
  4. Flagged when VLM reports anomaly_detected=True.
"""
from __future__ import annotations
from pathlib import Path
import cv2
import numpy as np
from core.zone import Zone
from tasks.base import BaseTask
from vlm.client import BaseVLMClient as VLMClient
from vlm.prompts import INSPECTION_PROMPT
from storage.local import LocalStore
import config

# Fraction of pixels that must change to trigger VLM (tune per deployment).
_DIFF_THRESHOLD = 0.05   # 5%
_BASELINES_DIR = config.DATA_DIR / "baselines"


class InspectionTask(BaseTask):
    def __init__(self, vlm: VLMClient, store: LocalStore) -> None:
        self.vlm = vlm
        self.store = store
        _BASELINES_DIR.mkdir(parents=True, exist_ok=True)

    def _baseline_path(self, zone: Zone) -> Path:
        return _BASELINES_DIR / f"{zone.id}.jpg"

    def _load_baseline(self, zone: Zone) -> np.ndarray | None:
        p = self._baseline_path(zone)
        if not p.exists():
            return None
        frame = cv2.imread(str(p))
        return frame

    def _save_baseline(self, zone: Zone, frame: np.ndarray) -> None:
        cv2.imwrite(str(self._baseline_path(zone)), frame)

    def _pixel_diff(self, baseline: np.ndarray, frame: np.ndarray) -> float:
        """Returns fraction of pixels that changed beyond a small threshold."""
        if baseline.shape != frame.shape:
            # Resize baseline to current frame size
            baseline = cv2.resize(baseline, (frame.shape[1], frame.shape[0]))
        diff = cv2.absdiff(baseline, frame)
        gray = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)
        _, mask = cv2.threshold(gray, 25, 255, cv2.THRESH_BINARY)
        changed = np.count_nonzero(mask)
        total = mask.size
        return changed / total

    async def run(self, frame: np.ndarray, zone: Zone, capture_id: str | None = None) -> None:
        baseline = self._load_baseline(zone)

        if baseline is None:
            # First frame — establish baseline, no evidence saved
            self._save_baseline(zone, frame)
            return

        diff_pct = self._pixel_diff(baseline, frame)

        if diff_pct < _DIFF_THRESHOLD:
            # Scene unchanged — skip VLM
            return

        result = await self.vlm.analyze(frame, INSPECTION_PROMPT)
        result["baseline_diff_pct"] = round(diff_pct * 100, 1)
        result["flagged"] = bool(result.get("anomaly_detected") or result.get("parse_error"))

        await self.store.save(frame, zone, task_type="inspection", result=result, capture_id=capture_id)

        # Update baseline if scene was inspected and passed (normal new state)
        if not result["flagged"]:
            self._save_baseline(zone, frame)

    def reset_baseline(self, zone: Zone) -> None:
        """Force-reset baseline for a zone (called from UI or API)."""
        self._baseline_path(zone).unlink(missing_ok=True)
