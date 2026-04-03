"""Classification task — identify cargo type in a zone frame."""
from __future__ import annotations
import numpy as np
from core.zone import Zone
from tasks.base import BaseTask
from vlm.client import BaseVLMClient as VLMClient
from vlm.prompts import CLASSIFICATION_PROMPT
from storage.local import LocalStore

VALID_TYPES = {
    "pallet_wrapped", "pallet_open", "single_box", "container",
    "bag", "drum", "mixed", "empty", "unknown",
}


class ClassificationTask(BaseTask):
    def __init__(self, vlm: VLMClient, store: LocalStore) -> None:
        self.vlm = vlm
        self.store = store

    async def run(self, frame: np.ndarray, zone: Zone, capture_id: str | None = None) -> None:
        result = await self.vlm.analyze(frame, CLASSIFICATION_PROMPT)

        # Normalise cargo_type in case VLM drifts
        if result.get("cargo_type") not in VALID_TYPES:
            result["cargo_type"] = "unknown"

        # Flag only when confidence is low or type is unknown — means the zone
        # saw something the model couldn't confidently classify
        result["flagged"] = (
            result.get("confidence") == "low"
            or result.get("cargo_type") == "unknown"
            or result.get("parse_error", False)
        )

        await self.store.save(frame, zone, task_type="classification", result=result, capture_id=capture_id)
