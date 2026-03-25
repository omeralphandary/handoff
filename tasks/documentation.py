"""Documentation task — condition evidence + PDF report."""
from __future__ import annotations
import numpy as np
from core.zone import Zone
from tasks.base import BaseTask
from vlm.client import BaseVLMClient as VLMClient
from vlm.prompts import DOCUMENTATION_PROMPT
from storage.local import LocalStore
from reports.pdf import generate_pdf


class DocumentationTask(BaseTask):
    def __init__(self, vlm: VLMClient, store: LocalStore) -> None:
        self.vlm = vlm
        self.store = store

    async def run(self, frame: np.ndarray, zone: Zone) -> None:
        result = await self.vlm.analyze(frame, DOCUMENTATION_PROMPT)
        record = await self.store.save(frame, zone, task_type="documentation", result=result)
        if result.get("damage_detected"):
            pdf_path = generate_pdf(record)
            await self.store.attach_pdf(record["id"], pdf_path)
