"""PDFSinkNode — always generates a PDF evidence report (useful for compliance flows)."""
from __future__ import annotations
import logging
from core.nodes.base import BaseNode, NodeMeta
from core.nodes.registry import NodeRegistry
from core.frame import Frame

log = logging.getLogger(__name__)


@NodeRegistry.register
class PDFSinkNode(BaseNode):
    META = NodeMeta(
        node_type="pdf_sink",
        label="PDF Report",
        category="sink",
        icon="📄",
        vram_mb=0,
        config_schema={
            "type": "object",
            "properties": {},
        },
    )

    async def process(self, frame: Frame) -> Frame | None:
        record_id: str | None = frame.metadata.get("record_id")
        if record_id is None:
            log.warning("[pdf_sink] no record_id in frame metadata — run SQLiteSinkNode first")
            return frame

        record = await self.ctx.store.get(record_id)
        if record is None:
            return frame

        from reports.pdf import generate_pdf
        pdf_path = generate_pdf(record)
        await self.ctx.store.attach_pdf(record_id, pdf_path)
        log.info("[pdf_sink] generated PDF: %s", pdf_path)
        return frame.with_meta(pdf_path=str(pdf_path))


from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from core.graph import ExecutionContext
