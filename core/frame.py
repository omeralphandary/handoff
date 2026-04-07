"""Frame — the unit of data that travels through the node graph."""
from __future__ import annotations
import time
import uuid
from dataclasses import dataclass, field
import numpy as np


@dataclass
class Frame:
    """
    Carries an image and accumulated metadata through the pipeline graph.
    Each node may enrich metadata; filter nodes return None to drop the frame.
    """
    image: np.ndarray
    source_id: str = ""
    capture_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: float = field(default_factory=time.time)
    # Accumulated by nodes as the frame travels the graph
    metadata: dict = field(default_factory=dict)

    def with_meta(self, **kwargs) -> "Frame":
        """Return a shallow copy with additional metadata merged in."""
        return Frame(
            image=self.image,
            source_id=self.source_id,
            capture_id=self.capture_id,
            timestamp=self.timestamp,
            metadata={**self.metadata, **kwargs},
        )
