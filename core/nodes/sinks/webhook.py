"""WebhookSinkNode — HTTP POST with configurable JSON payload."""
from __future__ import annotations
import json
import logging
import base64
import cv2
from core.nodes.base import BaseNode, NodeMeta
from core.nodes.registry import NodeRegistry
from core.frame import Frame

log = logging.getLogger(__name__)


@NodeRegistry.register
class WebhookSinkNode(BaseNode):
    META = NodeMeta(
        node_type="webhook_sink",
        label="Webhook",
        category="sink",
        icon="🔗",
        vram_mb=0,
        config_schema={
            "type": "object",
            "required": ["url"],
            "properties": {
                "url":          {"type": "string", "title": "Endpoint URL"},
                "include_image": {
                    "type": "boolean",
                    "title": "Include Image (base64)",
                    "default": False,
                    "description": "Attach the frame as base64 JPEG in the payload",
                },
                "headers": {
                    "type": "object",
                    "title": "Extra Headers",
                    "description": "e.g. {\"Authorization\": \"Bearer token\"}",
                    "default": {},
                },
                "timeout": {"type": "number", "title": "Timeout (s)", "default": 10},
            },
        },
    )

    def __init__(self, config: dict, ctx: "ExecutionContext") -> None:
        super().__init__(config, ctx)
        self._url: str = config["url"]
        self._include_image: bool = bool(config.get("include_image", False))
        self._headers: dict = config.get("headers", {})
        self._timeout: float = float(config.get("timeout", 10.0))

    async def process(self, frame: Frame) -> Frame | None:
        import httpx
        payload: dict = {
            "capture_id":  frame.capture_id,
            "source_id":   frame.source_id,
            "timestamp":   frame.timestamp,
            "zone_id":     self.ctx.zone.id,
            "zone_name":   self.ctx.zone.name,
            "result":      frame.metadata.get("inference_result"),
            "task_type":   frame.metadata.get("task_type"),
        }
        if self._include_image:
            _, buf = cv2.imencode(".jpg", frame.image, [cv2.IMWRITE_JPEG_QUALITY, 85])
            payload["image_b64"] = base64.b64encode(buf.tobytes()).decode()

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.post(self._url, json=payload, headers=self._headers)
                resp.raise_for_status()
            log.info("[webhook] posted capture %s → %s (%d)", frame.capture_id[:8], self._url, resp.status_code)
        except Exception as e:
            log.warning("[webhook] failed to post capture %s: %s", frame.capture_id[:8], e)

        return frame


from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from core.graph import ExecutionContext
