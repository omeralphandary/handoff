"""Placeholder nodes — visible in the palette, marked coming_soon, no-op at runtime."""
from __future__ import annotations
from core.nodes.base import BaseNode, NodeMeta
from core.nodes.registry import NodeRegistry
from core.frame import Frame


class _PlaceholderNode(BaseNode):
    """Passes frame through unchanged — used for coming-soon nodes."""
    async def process(self, frame: Frame) -> Frame | None:
        return frame


@NodeRegistry.register
class FaceDetectFilterNode(_PlaceholderNode):
    META = NodeMeta(
        node_type="face_detect",
        label="Face Detect",
        category="filter",
        coming_soon=True,
        config_schema={"type": "object", "properties": {}},
    )


@NodeRegistry.register
class ANPRFilterNode(_PlaceholderNode):
    META = NodeMeta(
        node_type="anpr",
        label="License Plate (ANPR)",
        category="filter",
        coming_soon=True,
        config_schema={"type": "object", "properties": {}},
    )


@NodeRegistry.register
class FireSmokeFilterNode(_PlaceholderNode):
    META = NodeMeta(
        node_type="fire_smoke",
        label="Fire / Smoke",
        category="filter",
        coming_soon=True,
        config_schema={"type": "object", "properties": {}},
    )


@NodeRegistry.register
class EmailSinkNode(_PlaceholderNode):
    META = NodeMeta(
        node_type="email_sink",
        label="Email",
        category="sink",
        coming_soon=True,
        config_schema={"type": "object", "properties": {}},
    )


@NodeRegistry.register
class WhatsAppSinkNode(_PlaceholderNode):
    META = NodeMeta(
        node_type="whatsapp_sink",
        label="WhatsApp",
        category="sink",
        coming_soon=True,
        config_schema={"type": "object", "properties": {}},
    )
