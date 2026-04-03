"""OCR task — extract labels, barcodes, and identifiers from a frame.

Pipeline:
  1. pyzbar  — fast barcode/QR decode (no GPU)
  2. EasyOCR — text extraction (GPU-accelerated when available)
  3. VLM     — structure and clean the raw reads into typed identifiers

The VLM step receives the raw OCR output in the prompt so it only needs to
parse and structure, not re-read. Flagged when nothing could be read at all
or when VLM parse fails.
"""
from __future__ import annotations
import logging
import numpy as np
from core.zone import Zone
from tasks.base import BaseTask
from vlm.client import BaseVLMClient as VLMClient
from storage.local import LocalStore
from tasks._ocr_readers import read_barcodes, read_text

log = logging.getLogger(__name__)


_CLEANUP_PROMPT_TEMPLATE = """You are reading shipping/logistics labels. Read ALL visible text in the image directly.
Also structure any barcodes already decoded below.

Pre-decoded barcodes/QR codes: {barcodes}

Read every visible text string from the image yourself, then return valid JSON only, no other text:
{{
  "texts": [str],
  "barcodes": [str],
  "identifiers": [{{"label": str, "value": str}}],
  "summary": str,
  "flagged": false
}}

Identifiers should extract typed values like tracking numbers, shipment IDs, weight, destination, HAZMAT codes.
If nothing meaningful was found, set flagged to true and explain in summary."""


class OCRTask(BaseTask):
    def __init__(self, vlm: VLMClient, store: LocalStore) -> None:
        self.vlm = vlm
        self.store = store

    async def run(self, frame: np.ndarray, zone: Zone, capture_id: str | None = None) -> None:
        # pyzbar only — no GPU, fast, reliable for barcodes/QR
        barcodes = read_barcodes(frame)
        log.info("[ocr] barcodes=%s", barcodes)

        # VLM reads all text directly — avoids EasyOCR VRAM conflict with Ollama
        prompt = _CLEANUP_PROMPT_TEMPLATE.format(
            texts=["(see image — use VLM to read all visible text)"],
            barcodes=barcodes or ["(none)"],
        )
        result = await self.vlm.analyze(frame, prompt)
        log.info("[ocr] vlm result=%s", result)

        if result.get("parse_error"):
            result["barcodes"] = barcodes
            result["flagged"] = True

        await self.store.save(frame, zone, task_type="ocr", result=result, capture_id=capture_id)
