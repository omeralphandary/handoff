"""SlackSinkNode — posts inference result + image to a Slack channel."""
from __future__ import annotations
import logging
import base64
import cv2
from core.nodes.base import BaseNode, NodeMeta
from core.nodes.registry import NodeRegistry
from core.frame import Frame

log = logging.getLogger(__name__)


@NodeRegistry.register
class SlackSinkNode(BaseNode):
    META = NodeMeta(
        node_type="slack_sink",
        label="Slack Alert",
        category="sink",
        icon="💬",
        vram_mb=0,
        config_schema={
            "type": "object",
            "required": ["webhook_url"],
            "properties": {
                "webhook_url": {
                    "type": "string",
                    "title": "Slack Incoming Webhook URL",
                },
                "only_flagged": {
                    "type": "boolean",
                    "title": "Only on Flagged",
                    "default": True,
                    "description": "Only post when the record is flagged (condition issue / anomaly)",
                },
                "mention": {
                    "type": "string",
                    "title": "Mention",
                    "default": "",
                    "description": "Slack user/channel to mention, e.g. @oncall or <!here>",
                },
            },
        },
    )

    def __init__(self, config: dict, ctx: "ExecutionContext") -> None:
        super().__init__(config, ctx)
        self._webhook_url: str = config["webhook_url"]
        self._only_flagged: bool = bool(config.get("only_flagged", True))
        self._mention: str = config.get("mention", "")

    async def process(self, frame: Frame) -> Frame | None:
        import httpx
        result = frame.metadata.get("inference_result", {})
        flagged = result.get("flagged") or result.get("condition_score", 5) < 4 or result.get("anomaly_detected")

        if self._only_flagged and not flagged:
            return frame

        summary = result.get("summary", "No summary available.")
        score = result.get("condition_score")
        score_str = f"Condition: {score}/5 — " if score is not None else ""
        mention = f"{self._mention} " if self._mention else ""

        text = (
            f"{mention}*Oversight Alert — {self.ctx.zone.name}*\n"
            f"{score_str}{summary}\n"
            f"capture: `{frame.capture_id[:8]}`"
        )
        payload = {"text": text}

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(self._webhook_url, json=payload)
                resp.raise_for_status()
            log.info("[slack] posted alert for capture %s", frame.capture_id[:8])
        except Exception as e:
            log.warning("[slack] failed to post: %s", e)

        return frame


from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from core.graph import ExecutionContext
