"""TimeOfDayFilterNode — passes frames only within configured hours."""
from __future__ import annotations
import datetime
from core.nodes.base import BaseNode, NodeMeta
from core.nodes.registry import NodeRegistry
from core.frame import Frame


@NodeRegistry.register
class TimeOfDayFilterNode(BaseNode):
    META = NodeMeta(
        node_type="time_of_day_filter",
        label="Time of Day",
        category="filter",
        icon="🕐",
        vram_mb=0,
        hidden=True,
        config_schema={
            "type": "object",
            "required": ["start_hour", "end_hour"],
            "properties": {
                "start_hour": {"type": "integer", "title": "Start Hour (0-23)", "default": 6},
                "end_hour":   {"type": "integer", "title": "End Hour (0-23)",   "default": 22},
            },
        },
    )

    def __init__(self, config: dict, ctx: "ExecutionContext") -> None:
        super().__init__(config, ctx)
        self._start: int = int(config.get("start_hour", 6))
        self._end: int = int(config.get("end_hour", 22))

    async def process(self, frame: Frame) -> Frame | None:
        now = datetime.datetime.now().hour
        if self._start <= self._end:
            active = self._start <= now < self._end
        else:
            # Wraps midnight: e.g. 22–06
            active = now >= self._start or now < self._end
        return frame if active else None


from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from core.graph import ExecutionContext
