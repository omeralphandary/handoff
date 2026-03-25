"""Zone definition and frame cropping."""
from __future__ import annotations
import cv2
import numpy as np
from dataclasses import dataclass, field


@dataclass
class Zone:
    id: str
    name: str
    camera_url: str
    # Normalized (0–1) polygon points [[x, y], ...]
    polygon: list[list[float]] = field(default_factory=list)
    task_type: str = "documentation"  # "ocr" | "documentation" | "inspection"
    retention_days: int = 90
    cooldown_seconds: float = 10.0

    def crop(self, frame: np.ndarray) -> np.ndarray:
        """Mask frame to polygon and return tight bounding-box crop."""
        if not self.polygon:
            return frame
        h, w = frame.shape[:2]
        pts = np.array(
            [[int(x * w), int(y * h)] for x, y in self.polygon], dtype=np.int32
        )
        mask = np.zeros((h, w), dtype=np.uint8)
        cv2.fillPoly(mask, [pts], 255)
        masked = cv2.bitwise_and(frame, frame, mask=mask)
        x, y, bw, bh = cv2.boundingRect(pts)
        return masked[y : y + bh, x : x + bw]
