"""MotionFilterNode — passes frames only when motion is detected."""
from __future__ import annotations
from core.nodes.base import BaseNode, NodeMeta
from core.nodes.registry import NodeRegistry
from core.motion import MotionTrigger
from core.frame import Frame


@NodeRegistry.register
class MotionFilterNode(BaseNode):
    META = NodeMeta(
        node_type="motion_filter",
        label="Motion Trigger",
        category="filter",
        icon="👁",
        vram_mb=0,
        hidden=True,
        config_schema={
            "type": "object",
            "properties": {
                "threshold_pct":    {"type": "number", "title": "Motion Threshold %", "default": 0.02},
                "cooldown_seconds": {"type": "number", "title": "Cooldown (s)",        "default": 10},
            },
        },
    )

    def __init__(self, config: dict, ctx: "ExecutionContext") -> None:
        super().__init__(config, ctx)
        self._trigger = MotionTrigger(
            threshold_pct=float(config.get("threshold_pct", 0.02)),
            cooldown_seconds=float(config.get("cooldown_seconds", 10.0)),
        )

    async def process(self, frame: Frame) -> Frame | None:
        if not self._trigger.check(frame.image):
            return None
        return frame.with_meta(trigger="motion")


from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from core.graph import ExecutionContext
