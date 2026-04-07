"""YOLO-based classification gate — runs locally before VLM tasks."""
from __future__ import annotations
import logging
import numpy as np

log = logging.getLogger(__name__)

# COCO classes relevant to logistics/dock environments
AVAILABLE_CLASSES = [
    "person", "truck", "car", "bus",
    "motorcycle", "bicycle",
    "suitcase", "backpack", "bottle", "chair",
]


class YOLOGate:
    """
    Runs YOLOv8n locally and returns which trigger classes were detected.
    Model is loaded once and reused. ~50ms per frame on GPU, ~200ms CPU.
    """

    def __init__(self, classes: list[str], confidence: float = 0.4) -> None:
        self.classes = {c.lower() for c in classes}
        self.confidence = confidence
        self._model = None  # lazy-load on first check

    def _load(self) -> None:
        if self._model is not None:
            return
        try:
            from ultralytics import YOLO
            self._model = YOLO("yolov8n.pt")
            log.info("[yolo] model loaded (yolov8n)")
        except ImportError:
            raise RuntimeError("ultralytics not installed — run: pip install ultralytics")

    def check(self, frame: np.ndarray) -> list[str]:
        """Returns matched class names, empty list if none detected."""
        self._load()
        results = self._model(frame, verbose=False, conf=self.confidence)
        matched: list[str] = []
        for r in results:
            for cls_id, conf in zip(r.boxes.cls, r.boxes.conf):
                name = self._model.names[int(cls_id)].lower()
                if name in self.classes and float(conf) >= self.confidence:
                    if name not in matched:
                        matched.append(name)
        return matched
