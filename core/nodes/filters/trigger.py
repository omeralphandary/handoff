"""Unified TriggerFilterNode — manual / motion / interval / by_class in one node."""
from __future__ import annotations
import time
import logging
from core.nodes.base import BaseNode, NodeMeta
from core.nodes.registry import NodeRegistry
from core.frame import Frame

log = logging.getLogger(__name__)


try:
    from core.yolo_gate import AVAILABLE_CLASSES
except Exception:
    AVAILABLE_CLASSES = []


@NodeRegistry.register
class TriggerFilterNode(BaseNode):
    META = NodeMeta(
        node_type="trigger",
        label="Trigger",
        category="filter",
        icon="trigger",
        vram_mb=0,   # overridden at __init__ when mode==by_class
        config_schema={
            "type": "object",
            "properties": {
                "mode": {
                    "type": "string",
                    "title": "Trigger Mode",
                    "enum": ["manual", "motion", "interval", "by_class"],
                    "default": "manual",
                    "description": "manual: only via Trigger button · motion: pixel-diff gate · interval: every N seconds · by_class: YOLO class detection",
                },
                "threshold_pct": {
                    "type": "number",
                    "title": "Motion Threshold %",
                    "default": 0.02,
                    "description": "Used by motion and by_class modes",
                },
                "cooldown_seconds": {
                    "type": "number",
                    "title": "Cooldown (s)",
                    "default": 10.0,
                    "description": "Used by motion and by_class modes",
                },
                "interval_seconds": {
                    "type": "number",
                    "title": "Interval (s)",
                    "default": 60.0,
                    "description": "Used by interval mode",
                },
                "classes": {
                    "type": "array",
                    "title": "Target Classes",
                    "items": {"type": "string", "enum": AVAILABLE_CLASSES},
                    "description": "Used by by_class mode — YOLO target classes",
                },
                "confidence": {
                    "type": "number",
                    "title": "YOLO Confidence",
                    "default": 0.4,
                    "description": "Used by by_class mode",
                },
            },
        },
    )

    def __init__(self, config: dict, ctx: "ExecutionContext") -> None:
        super().__init__(config, ctx)
        self._mode: str = config.get("mode", "manual")

        if self._mode == "motion":
            from core.motion import MotionTrigger
            self._motion = MotionTrigger(
                threshold_pct=float(config.get("threshold_pct", 0.02)),
                cooldown_seconds=float(config.get("cooldown_seconds", 10.0)),
            )

        elif self._mode == "interval":
            self._interval: float = float(config.get("interval_seconds", 60.0))
            self._last_trigger: float = 0.0

        elif self._mode == "by_class":
            from core.yolo_gate import YOLOGate
            from core.motion import MotionTrigger
            classes = config.get("classes") or []
            self._gate = YOLOGate(classes, confidence=float(config.get("confidence", 0.4)))
            self._motion = MotionTrigger(
                threshold_pct=float(config.get("threshold_pct", 0.02)),
                cooldown_seconds=float(config.get("cooldown_seconds", 10.0)),
            )
            # YOLO needs GPU — reflect in VRAM (can't mutate META, store per-instance)
            self._vram_mb_override = 200

    async def setup(self) -> None:
        if self._mode == "by_class":
            loop = __import__("asyncio").get_event_loop()
            await loop.run_in_executor(None, self._gate.load)

    async def process(self, frame: Frame) -> Frame | None:
        if self._mode == "manual":
            return frame if frame.metadata.get("_manual_trigger") else None

        if self._mode == "motion":
            if not self._motion.check(frame.image):
                return None
            return frame.with_meta(trigger="motion")

        if self._mode == "interval":
            now = time.time()
            if now - self._last_trigger < self._interval:
                return None
            self._last_trigger = now
            return frame.with_meta(trigger="interval")

        if self._mode == "by_class":
            if not self._motion.check(frame.image):
                return None
            loop = __import__("asyncio").get_event_loop()
            detected = await loop.run_in_executor(None, self._gate.detect, frame.image)
            if not detected:
                return None
            return frame.with_meta(trigger="by_class", detected_classes=detected)

        return None


from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from core.graph import ExecutionContext
