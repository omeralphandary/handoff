"""SQLiteSinkNode — persists inference results to the evidence table."""
from __future__ import annotations
import logging
from core.nodes.base import BaseNode, NodeMeta
from core.nodes.registry import NodeRegistry
from core.frame import Frame

log = logging.getLogger(__name__)


@NodeRegistry.register
class SQLiteSinkNode(BaseNode):
    META = NodeMeta(
        node_type="sqlite_sink",
        label="Save to SQLite",
        category="sink",
        icon="💾",
        vram_mb=0,
        config_schema={
            "type": "object",
            "properties": {
                "attach_pdf_on_flag": {
                    "type": "boolean",
                    "title": "Generate PDF on Flag",
                    "default": True,
                    "description": "Auto-generate PDF evidence report when record is flagged",
                },
            },
        },
    )

    def __init__(self, config: dict, ctx: "ExecutionContext") -> None:
        super().__init__(config, ctx)
        self._attach_pdf: bool = bool(config.get("attach_pdf_on_flag", True))

    async def process(self, frame: Frame) -> Frame | None:
        result: dict | None = frame.metadata.get("inference_result")
        task_type: str = frame.metadata.get("task_type", "documentation")
        if result is None:
            log.warning("[sqlite_sink] no inference_result in frame metadata — skipping")
            return frame

        # Inject triggered_by from YOLO metadata if present
        triggered_by = frame.metadata.get("triggered_by")
        if triggered_by:
            result = {**result, "triggered_by": triggered_by}

        record = await self.ctx.store.save(
            frame=frame.image,
            zone=self.ctx.zone,
            task_type=task_type,
            result=result,
            capture_id=frame.capture_id,
        )
        log.info("[sqlite_sink] saved record %s (flagged=%s)", record["id"][:8], record["flagged"])

        if self._attach_pdf and record["flagged"]:
            from reports.pdf import generate_pdf
            pdf_path = generate_pdf(record)
            await self.ctx.store.attach_pdf(record["id"], pdf_path)

        return frame.with_meta(record_id=record["id"], saved=True)


from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from core.graph import ExecutionContext
