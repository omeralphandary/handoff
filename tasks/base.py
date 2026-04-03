"""Abstract base task."""
from __future__ import annotations
from abc import ABC, abstractmethod
import numpy as np
from core.zone import Zone


class BaseTask(ABC):
    @abstractmethod
    async def run(self, frame: np.ndarray, zone: Zone, capture_id: str | None = None) -> None:
        """Process a triggered frame and persist the evidence record."""
        ...
