"""CropFilterNode — masks frame to a polygon and returns tight bounding-box crop."""
from __future__ import annotations
import cv2
import numpy as np
from core.nodes.base import BaseNode, NodeMeta
from core.nodes.registry import NodeRegistry
from core.frame import Frame


@NodeRegistry.register
class CropFilterNode(BaseNode):
    META = NodeMeta(
        node_type="crop_filter",
        label="Crop / ROI",
        category="filter",
        icon="✂️",
        vram_mb=0,
        config_schema={
            "type": "object",
            "properties": {
                "polygon": {
                    "type": "array",
                    "title": "Polygon",
                    "description": "Normalized [[x,y],...] points (0-1)",
                    "items": {"type": "array", "items": {"type": "number"}, "minItems": 2, "maxItems": 2},
                },
            },
        },
    )

    def __init__(self, config: dict, ctx: "ExecutionContext") -> None:
        super().__init__(config, ctx)
        self._polygon: list[list[float]] = config.get("polygon", [])

    async def process(self, frame: Frame) -> Frame | None:
        if not self._polygon:
            return frame
        img = frame.image
        h, w = img.shape[:2]
        pts = np.array(
            [[int(x * w), int(y * h)] for x, y in self._polygon], dtype=np.int32
        )
        mask = np.zeros((h, w), dtype=np.uint8)
        cv2.fillPoly(mask, [pts], 255)
        masked = cv2.bitwise_and(img, img, mask=mask)
        x, y, bw, bh = cv2.boundingRect(pts)
        cropped = masked[y: y + bh, x: x + bw]
        return Frame(
            image=cropped,
            source_id=frame.source_id,
            capture_id=frame.capture_id,
            timestamp=frame.timestamp,
            metadata={**frame.metadata, "cropped": True},
        )


from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from core.graph import ExecutionContext
