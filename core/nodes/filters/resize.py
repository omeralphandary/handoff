"""ResizeFilterNode — resizes frames before inference (cost/latency control)."""
from __future__ import annotations
import cv2
from core.nodes.base import BaseNode, NodeMeta
from core.nodes.registry import NodeRegistry
from core.frame import Frame


@NodeRegistry.register
class ResizeFilterNode(BaseNode):
    META = NodeMeta(
        node_type="resize_filter",
        label="Resize",
        category="filter",
        icon="⤡",
        vram_mb=0,
        hidden=True,
        config_schema={
            "type": "object",
            "properties": {
                "max_width":  {"type": "integer", "title": "Max Width (px)",  "default": 1280},
                "max_height": {"type": "integer", "title": "Max Height (px)", "default": 720},
            },
        },
    )

    def __init__(self, config: dict, ctx: "ExecutionContext") -> None:
        super().__init__(config, ctx)
        self._max_w: int = int(config.get("max_width", 1280))
        self._max_h: int = int(config.get("max_height", 720))

    async def process(self, frame: Frame) -> Frame | None:
        h, w = frame.image.shape[:2]
        if w <= self._max_w and h <= self._max_h:
            return frame
        scale = min(self._max_w / w, self._max_h / h)
        new_w = int(w * scale)
        new_h = int(h * scale)
        resized = cv2.resize(frame.image, (new_w, new_h), interpolation=cv2.INTER_AREA)
        return Frame(
            image=resized,
            source_id=frame.source_id,
            capture_id=frame.capture_id,
            timestamp=frame.timestamp,
            metadata={**frame.metadata, "resized_from": (w, h)},
        )


from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from core.graph import ExecutionContext
