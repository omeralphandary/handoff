"""YOLOFilterNode — passes frames only when target classes are detected."""
from __future__ import annotations
import asyncio
import logging
from core.nodes.base import BaseNode, NodeMeta
from core.nodes.registry import NodeRegistry
from core.yolo_gate import YOLOGate, AVAILABLE_CLASSES
from core.motion import MotionTrigger
from core.frame import Frame

log = logging.getLogger(__name__)


@NodeRegistry.register
class YOLOFilterNode(BaseNode):
    META = NodeMeta(
        node_type="yolo_filter",
        label="YOLO Class Gate",
        category="filter",
        icon="🎯",
        vram_mb=200,
        hidden=True,
        config_schema={
            "type": "object",
            "required": ["classes"],
            "properties": {
                "classes": {
                    "type": "array",
                    "title": "Target Classes",
                    "items": {"type": "string", "enum": AVAILABLE_CLASSES},
                    "description": "Only pass frames containing these YOLO classes",
                },
                "confidence":       {"type": "number", "title": "Confidence", "default": 0.4},
                "cooldown_seconds": {"type": "number", "title": "Cooldown (s)", "default": 10},
                "motion_prefilter": {"type": "boolean", "title": "Motion Pre-filter", "default": True},
                "threshold_pct":    {"type": "number", "title": "Motion Threshold %", "default": 0.02},
            },
        },
    )

    def __init__(self, config: dict, ctx: "ExecutionContext") -> None:
        super().__init__(config, ctx)
        self._gate = YOLOGate(
            classes=config.get("classes", []),
            confidence=float(config.get("confidence", 0.4)),
        )
        self._cooldown = float(config.get("cooldown_seconds", 10.0))
        self._motion_prefilter = bool(config.get("motion_prefilter", True))
        self._motion = MotionTrigger(
            threshold_pct=float(config.get("threshold_pct", 0.02)),
            cooldown_seconds=self._cooldown,
        )

    async def process(self, frame: Frame) -> Frame | None:
        # Cheap motion pre-filter to avoid running YOLO on static frames
        if self._motion_prefilter:
            if self._motion.in_cooldown():
                return None
            if not self._motion.has_motion(frame.image):
                return None

        loop = asyncio.get_event_loop()
        matched = await loop.run_in_executor(None, self._gate.check, frame.image)
        if not matched:
            log.debug("[yolo_filter] no target class (watching: %s)", sorted(self._gate.classes))
            return None

        log.info("[yolo_filter] classes confirmed: %s", matched)
        self._motion.stamp_cooldown()
        return frame.with_meta(trigger="by_class", triggered_by=matched)


from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from core.graph import ExecutionContext
