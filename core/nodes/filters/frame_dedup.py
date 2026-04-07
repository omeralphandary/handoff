"""FrameDedupFilterNode — drops frames where the scene hasn't changed enough."""
from __future__ import annotations
import cv2
import numpy as np
from core.nodes.base import BaseNode, NodeMeta
from core.nodes.registry import NodeRegistry
from core.frame import Frame


@NodeRegistry.register
class FrameDedupFilterNode(BaseNode):
    META = NodeMeta(
        node_type="frame_dedup_filter",
        label="Frame Dedup",
        category="filter",
        icon="⏭",
        vram_mb=0,
        hidden=True,
        config_schema={
            "type": "object",
            "properties": {
                "threshold": {
                    "type": "number",
                    "title": "Change Threshold (0-1)",
                    "default": 0.05,
                    "description": "Fraction of pixels that must differ to pass the frame",
                },
            },
        },
    )

    def __init__(self, config: dict, ctx: "ExecutionContext") -> None:
        super().__init__(config, ctx)
        self._threshold: float = float(config.get("threshold", 0.05))
        self._last: np.ndarray | None = None

    async def process(self, frame: Frame) -> Frame | None:
        gray = cv2.cvtColor(frame.image, cv2.COLOR_BGR2GRAY)
        if self._last is None:
            self._last = gray
            return frame
        diff = cv2.absdiff(gray, self._last)
        changed = np.count_nonzero(diff > 25) / diff.size
        if changed < self._threshold:
            return None
        self._last = gray
        return frame


from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from core.graph import ExecutionContext
