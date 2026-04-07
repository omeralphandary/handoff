"""Graph template builder — converts a Zone config to a GraphDefinition."""
from __future__ import annotations
from core.graph import GraphDefinition, NodeDef, EdgeDef
from core.zone import Zone

_MODE_MAP = {"sequence": "interval", "by_class": "by_class",
             "motion": "motion", "manual": "manual"}


def default_graph_from_zone(zone: Zone) -> GraphDefinition:
    """
    Build a GraphDefinition from a Zone.

    Pipeline shape:
      camera_source → [crop_filter] → trigger → inference × task_types → sqlite_sink
    """
    import config as cfg

    nodes: list[NodeDef] = []
    edges: list[EdgeDef] = []

    # ── Source ────────────────────────────────────────────────────────────────
    nodes.append(NodeDef(
        id="source",
        type="camera_source",
        config={"url": zone.camera_url, "fps_limit": 10.0, "source_id": zone.id},
    ))
    prev = "source"

    # ── Crop (optional) ───────────────────────────────────────────────────────
    if zone.polygon:
        nodes.append(NodeDef(id="crop", type="crop_filter", config={"polygon": zone.polygon}))
        edges.append(EdgeDef(source=prev, target="crop"))
        prev = "crop"

    # ── Unified trigger node ──────────────────────────────────────────────────
    nodes.append(NodeDef(
        id="trigger",
        type="trigger",
        config={
            "mode":             _MODE_MAP.get(zone.trigger_mode, "manual"),
            "threshold_pct":    zone.motion_threshold,
            "cooldown_seconds": zone.cooldown_seconds,
            "interval_seconds": zone.sequence_interval or 60.0,
            "classes":          zone.trigger_classes,
        },
    ))
    edges.append(EdgeDef(source=prev, target="trigger"))
    prev = "trigger"

    # ── Inference node (one, supports multiple task types) ────────────────────
    backend = getattr(cfg, "VLM_BACKEND", "anthropic")
    node_type = "claude_inference" if backend == "anthropic" else "ollama_inference"
    nodes.append(NodeDef(
        id="infer",
        type=node_type,
        config={"task_types": zone.task_types},
    ))
    edges.append(EdgeDef(source=prev, target="infer"))

    # ── SQLite sink ───────────────────────────────────────────────────────────
    nodes.append(NodeDef(id="sink", type="sqlite_sink", config={"attach_pdf_on_flag": True}))
    edges.append(EdgeDef(source="infer", target="sink"))

    return GraphDefinition(nodes=nodes, edges=edges)
