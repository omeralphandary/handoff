"""Node system — pluggable building blocks for vision pipelines."""
from core.nodes.base import BaseNode, SourceNode, NodeMeta
from core.nodes.registry import NodeRegistry

# Import all node implementations so they self-register via @NodeRegistry.register
# Sources
import core.nodes.sources.camera          # noqa: F401
import core.nodes.sources.video_file      # noqa: F401
import core.nodes.sources.image_folder    # noqa: F401
# Filters
import core.nodes.filters.trigger         # noqa: F401  ← unified trigger node
import core.nodes.filters.manual_trigger  # noqa: F401  (kept for backward compat)
import core.nodes.filters.motion          # noqa: F401  (kept for backward compat)
import core.nodes.filters.yolo            # noqa: F401  (kept for backward compat)
import core.nodes.filters.crop            # noqa: F401
import core.nodes.filters.time_interval   # noqa: F401  (kept for backward compat)
import core.nodes.filters.time_of_day     # noqa: F401  (kept for backward compat)
import core.nodes.filters.frame_dedup     # noqa: F401
# brightness and resize dropped per product decision
# Inference
import core.nodes.inference.vlm           # noqa: F401
import core.nodes.inference.gemini        # noqa: F401
import core.nodes.inference.custom_prompt # noqa: F401
# Sinks
import core.nodes.placeholders            # noqa: F401
import core.nodes.sinks.sqlite            # noqa: F401
import core.nodes.sinks.pdf               # noqa: F401
import core.nodes.sinks.webhook           # noqa: F401
import core.nodes.sinks.slack             # noqa: F401
import core.nodes.sinks.s3               # noqa: F401
import core.nodes.sinks.mqtt              # noqa: F401

__all__ = ["BaseNode", "SourceNode", "NodeMeta", "NodeRegistry"]
