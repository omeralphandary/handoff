"""TimeIntervalFilterNode — passes one frame per interval, drops the rest."""
from __future__ import annotations
import time
from core.nodes.base import BaseNode, NodeMeta
from core.nodes.registry import NodeRegistry
from core.frame import Frame


@NodeRegistry.register
class TimeIntervalFilterNode(BaseNode):
    META = NodeMeta(
        node_type="time_interval_filter",
        label="Time Interval",
        category="filter",
        icon="⏱",
        vram_mb=0,
        hidden=True,
        config_schema={
            "type": "object",
            "required": ["interval_seconds"],
            "properties": {
                "interval_seconds": {
                    "type": "number",
                    "title": "Interval (s)",
                    "default": 60,
                    "description": "Minimum seconds between triggered frames",
                },
            },
        },
    )

    def __init__(self, config: dict, ctx: "ExecutionContext") -> None:
        super().__init__(config, ctx)
        self._interval: float = float(config.get("interval_seconds", 60.0))
        self._last_trigger: float = 0.0

    async def process(self, frame: Frame) -> Frame | None:
        now = time.time()
        if now - self._last_trigger < self._interval:
            return None
        self._last_trigger = now
        return frame


from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from core.graph import ExecutionContext
