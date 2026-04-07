"""ManualTriggerFilterNode — drops all frames except those explicitly fired via trigger_now()."""
from __future__ import annotations
from core.nodes.base import BaseNode, NodeMeta
from core.nodes.registry import NodeRegistry
from core.frame import Frame


@NodeRegistry.register
class ManualTriggerFilterNode(BaseNode):
    META = NodeMeta(
        node_type="manual_trigger",
        label="Manual Trigger",
        category="filter",
        icon="manual_trigger",
        vram_mb=0,
        hidden=True,
        config_schema={
            "type": "object",
            "properties": {},
        },
    )

    async def process(self, frame: Frame) -> Frame | None:
        # Only frames tagged by GraphExecutor.trigger_now() pass through.
        # The run loop's frames are silently dropped.
        if frame.metadata.get("_manual_trigger"):
            return frame
        return None
