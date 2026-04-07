"""CameraSourceNode — wraps CameraStream as a SourceNode."""
from __future__ import annotations
from core.nodes.base import SourceNode, NodeMeta
from core.nodes.registry import NodeRegistry
from core.camera import CameraStream
from core.frame import Frame


@NodeRegistry.register
class CameraSourceNode(SourceNode):
    META = NodeMeta(
        node_type="camera_source",
        label="IP Camera",
        category="source",
        icon="📷",
        vram_mb=0,
        config_schema={
            "type": "object",
            "required": ["url"],
            "properties": {
                "url":       {"type": "string", "title": "RTSP URL"},
                "fps_limit": {"type": "number", "title": "FPS Limit", "default": 10},
                "source_id": {"type": "string", "title": "Source ID"},
            },
        },
    )

    def __init__(self, config: dict, ctx: "ExecutionContext") -> None:
        super().__init__(config, ctx)
        self._stream = CameraStream(
            url=config["url"],
            fps_limit=float(config.get("fps_limit", 10.0)),
        )
        self._source_id: str = config.get("source_id", config["url"])

    def start(self) -> None:
        self._stream.start()

    def stop(self) -> None:
        self._stream.stop()

    def latest_frame(self) -> Frame | None:
        raw = self._stream.latest_frame()
        if raw is None:
            return None
        return Frame(image=raw, source_id=self._source_id)

    @property
    def last_frame_time(self) -> float:
        return self._stream.last_frame_time


from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from core.graph import ExecutionContext
