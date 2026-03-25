"""Motion trigger — fires when significant change detected in zone."""
from __future__ import annotations
import time
import cv2
import numpy as np


class MotionTrigger:
    """
    Background subtraction trigger.
    Returns True if motion pixels exceed threshold % of zone area.
    Enforces a cooldown between triggers.
    """

    def __init__(
        self,
        threshold_pct: float = 0.02,
        cooldown_seconds: float = 10.0,
    ) -> None:
        self.threshold_pct = threshold_pct
        self.cooldown_seconds = cooldown_seconds
        self._subtractor = cv2.createBackgroundSubtractorMOG2(
            history=200, varThreshold=40, detectShadows=False
        )
        self._last_trigger: float = 0.0

    def check(self, frame: np.ndarray) -> bool:
        """Returns True if motion detected and cooldown has elapsed."""
        if time.time() - self._last_trigger < self.cooldown_seconds:
            return False
        mask = self._subtractor.apply(frame)
        motion_ratio = np.count_nonzero(mask) / mask.size
        if motion_ratio >= self.threshold_pct:
            self._last_trigger = time.time()
            return True
        return False
