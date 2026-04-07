"""BrightnessFilterNode — rejects frames that are too dark or overexposed."""
from __future__ import annotations
import cv2
import numpy as np
from core.nodes.base import BaseNode, NodeMeta
from core.nodes.registry import NodeRegistry
from core.frame import Frame


@NodeRegistry.register
class BrightnessFilterNode(BaseNode):
    META = NodeMeta(
        node_type="brightness_filter",
        label="Brightness Gate",
        category="filter",
        icon="☀",
        vram_mb=0,
        hidden=True,
        config_schema={
            "type": "object",
            "properties": {
                "min_brightness": {"type": "integer", "title": "Min Brightness (0-255)", "default": 20},
                "max_brightness": {"type": "integer", "title": "Max Brightness (0-255)", "default": 235},
            },
        },
    )

    def __init__(self, config: dict, ctx: "ExecutionContext") -> None:
        super().__init__(config, ctx)
        self._min: int = int(config.get("min_brightness", 20))
        self._max: int = int(config.get("max_brightness", 235))

    async def process(self, frame: Frame) -> Frame | None:
        gray = cv2.cvtColor(frame.image, cv2.COLOR_BGR2GRAY)
        mean = float(np.mean(gray))
        if mean < self._min or mean > self._max:
            return None
        return frame


from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from core.graph import ExecutionContext
