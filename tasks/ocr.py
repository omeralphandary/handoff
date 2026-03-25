"""OCR task — extract labels, barcodes, IDs from frame."""
from __future__ import annotations
import numpy as np
from core.zone import Zone
from tasks.base import BaseTask
from vlm.client import BaseVLMClient as VLMClient
from vlm.prompts import OCR_PROMPT
from storage.local import LocalStore


class OCRTask(BaseTask):
    def __init__(self, vlm: VLMClient, store: LocalStore) -> None:
        self.vlm = vlm
        self.store = store

    async def run(self, frame: np.ndarray, zone: Zone) -> None:
        result = await self.vlm.analyze(frame, OCR_PROMPT)
        await self.store.save(frame, zone, task_type="ocr", result=result)
