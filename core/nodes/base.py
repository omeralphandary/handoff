"""Base classes for all node types."""
from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any
import numpy as np
from core.frame import Frame


@dataclass
class NodeMeta:
    """Static metadata declared by each node class."""
    node_type: str
    label: str
    category: str          # "source" | "filter" | "inference" | "sink"
    icon: str = "⬡"
    vram_mb: int = 0       # estimated VRAM at runtime (0 = CPU / cloud)
    config_schema: dict = field(default_factory=dict)  # JSON Schema for config fields
    hidden: bool = False        # if True, excluded from palette catalog (still executable)
    coming_soon: bool = False   # if True, shown in palette but marked as not yet implemented


class BaseNode(ABC):
    """
    Processing node — receives a Frame, returns an enriched Frame or None (drop).
    Nodes are stateless with respect to the graph; all state lives in instance vars
    set during __init__ from the config dict.
    """
    META: NodeMeta  # must be defined on every concrete subclass

    def __init__(self, config: dict, ctx: "ExecutionContext") -> None:
        self.config = config
        self.ctx = ctx

    @abstractmethod
    async def process(self, frame: Frame) -> Frame | None:
        """Return enriched Frame to continue, None to drop."""
        ...

    async def setup(self) -> None:
        """Called once before the graph starts. Override for async init."""

    async def teardown(self) -> None:
        """Called once after the graph stops. Override for cleanup."""


class SourceNode(ABC):
    """
    Frame producer — runs a background thread/loop and exposes latest_frame().
    One per graph (a graph has exactly one source).
    """
    META: NodeMeta

    def __init__(self, config: dict, ctx: "ExecutionContext") -> None:
        self.config = config
        self.ctx = ctx

    @abstractmethod
    def start(self) -> None: ...

    @abstractmethod
    def stop(self) -> None: ...

    @abstractmethod
    def latest_frame(self) -> Frame | None: ...

    @property
    @abstractmethod
    def last_frame_time(self) -> float: ...


# Avoid circular import — ExecutionContext imported at runtime only
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from core.graph import ExecutionContext
