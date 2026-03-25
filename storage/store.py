"""Abstract evidence store interface."""
from __future__ import annotations
from abc import ABC, abstractmethod
from pathlib import Path
import numpy as np
from core.zone import Zone


class BaseStore(ABC):
    @abstractmethod
    async def save(
        self,
        frame: np.ndarray,
        zone: Zone,
        task_type: str,
        result: dict,
    ) -> dict:
        """Persist image + metadata. Returns the saved EvidenceRecord as dict."""
        ...

    @abstractmethod
    async def get(self, record_id: str) -> dict | None: ...

    @abstractmethod
    async def list(
        self,
        zone_id: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict]: ...

    @abstractmethod
    async def attach_pdf(self, record_id: str, pdf_path: Path) -> None: ...

    @abstractmethod
    async def purge_expired(self) -> int:
        """Delete records past their retention window. Returns count deleted."""
        ...
