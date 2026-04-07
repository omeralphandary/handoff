"""NodeRegistry — catalog of all available node types."""
from __future__ import annotations
from typing import Type
from core.nodes.base import BaseNode, SourceNode, NodeMeta


class NodeRegistry:
    _nodes: dict[str, Type[BaseNode | SourceNode]] = {}

    @classmethod
    def register(cls, klass: Type[BaseNode | SourceNode]) -> Type[BaseNode | SourceNode]:
        """Decorator — register a node class by its META.node_type."""
        cls._nodes[klass.META.node_type] = klass
        return klass

    @classmethod
    def get(cls, node_type: str) -> Type[BaseNode | SourceNode]:
        if node_type not in cls._nodes:
            raise KeyError(f"Unknown node type: {node_type!r}. Registered: {list(cls._nodes)}")
        return cls._nodes[node_type]

    @classmethod
    def catalog(cls) -> list[dict]:
        """Return all registered node types as serializable dicts (for GET /nodes)."""
        result = []
        for klass in cls._nodes.values():
            m: NodeMeta = klass.META
            if m.hidden:
                continue
            result.append({
                "type":          m.node_type,
                "label":         m.label,
                "category":      m.category,
                "icon":          m.icon,
                "vram_mb":       m.vram_mb,
                "config_schema": m.config_schema,
                "coming_soon":   m.coming_soon,
            })
        return sorted(result, key=lambda x: x["category"])

    @classmethod
    def instantiate(
        cls, node_type: str, config: dict, ctx: "ExecutionContext"
    ) -> "BaseNode | SourceNode":
        return cls.get(node_type)(config, ctx)


# Avoid circular import
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from core.graph import ExecutionContext
