"""GraphDefinition + GraphExecutor — replaces ZoneDispatcher."""
from __future__ import annotations
import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from typing import Any

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# ExecutionContext — shared resources injected into every node
# ---------------------------------------------------------------------------

@dataclass
class ExecutionContext:
    zone: Any          # core.zone.Zone
    store: Any         # storage.local.LocalStore
    vlm: Any = None    # vlm.client.BaseVLMClient (optional; nodes that need it init lazily)


# ---------------------------------------------------------------------------
# GraphDefinition — JSON-serializable DAG description
# ---------------------------------------------------------------------------

@dataclass
class NodeDef:
    id: str
    type: str                         # NodeRegistry key
    config: dict = field(default_factory=dict)


@dataclass
class EdgeDef:
    source: str   # node id
    target: str   # node id


@dataclass
class GraphDefinition:
    nodes: list[NodeDef] = field(default_factory=list)
    edges: list[EdgeDef] = field(default_factory=list)

    @classmethod
    def from_dict(cls, d: dict) -> "GraphDefinition":
        return cls(
            nodes=[NodeDef(**n) for n in d.get("nodes", [])],
            edges=[EdgeDef(source=e["source"], target=e["target"]) for e in d.get("edges", [])],
        )

    def to_dict(self) -> dict:
        return {
            "nodes": [{"id": n.id, "type": n.type, "config": n.config} for n in self.nodes],
            "edges": [{"source": e.source, "target": e.target} for e in self.edges],
        }


# ---------------------------------------------------------------------------
# GraphExecutor
# ---------------------------------------------------------------------------

class GraphExecutor:
    """
    Executes a GraphDefinition.

    Backward-compat shim with ZoneDispatcher:
      - self._stream      → the SourceNode instance
      - self.is_inferring → bool flag
      - trigger_now()     → grabs current frame, runs the full graph immediately
      - run()             → async main loop
    """

    def __init__(self, graph_def: GraphDefinition, ctx: ExecutionContext) -> None:
        from core.nodes.registry import NodeRegistry
        from core.nodes.base import SourceNode, BaseNode

        self._ctx = ctx
        self._graph_def = graph_def
        self.is_inferring: bool = False
        self.last_capture_id: str | None = None

        # Instantiate all nodes
        self._node_map: dict[str, SourceNode | BaseNode] = {}
        for nd in graph_def.nodes:
            self._node_map[nd.id] = NodeRegistry.instantiate(nd.type, nd.config, ctx)

        # Find the single SourceNode
        source_nodes = [
            (nid, n) for nid, n in self._node_map.items()
            if isinstance(n, SourceNode)
        ]
        if len(source_nodes) != 1:
            raise ValueError(f"GraphExecutor requires exactly one SourceNode, found {len(source_nodes)}")
        self._source_id, self._source = source_nodes[0]

        # Build adjacency list (node_id → list of successor node_ids)
        self._adj: dict[str, list[str]] = {nid: [] for nid in self._node_map}
        for edge in graph_def.edges:
            self._adj[edge.source].append(edge.target)

        # Topological order of processing nodes (excluding source)
        self._topo_order: list[str] = self._topo_sort()

        # Hybrid mode detection: local_id → cloud_id pairs sharing a trigger parent.
        # local always runs first; cloud is the fallback.
        self._hybrid_pairs: dict[str, str] = self._detect_hybrid_pairs()
        if self._hybrid_pairs:
            self._topo_order = self._reorder_for_hybrid(self._topo_order)
            log.info(
                "[graph] hybrid mode detected — %d pair(s): %s",
                len(self._hybrid_pairs),
                [(l, c) for l, c in self._hybrid_pairs.items()],
            )

        # VRAM budget — sum across all nodes (3.7)
        self.vram_required_mb: int = sum(
            n.META.vram_mb for n in self._node_map.values()
        )

    # ── backward compat: dashboard routes read dispatcher._stream ────────────
    @property
    def _stream(self):
        return self._source

    # ── Topological sort (Kahn's algorithm) ──────────────────────────────────

    def _topo_sort(self) -> list[str]:
        """Return processing node IDs in topological order (source excluded)."""
        in_degree: dict[str, int] = {nid: 0 for nid in self._node_map if nid != self._source_id}
        for src, targets in self._adj.items():
            if src == self._source_id:
                continue
            for t in targets:
                if t in in_degree:
                    in_degree[t] += 1

        queue = [nid for nid, deg in in_degree.items() if deg == 0]
        order: list[str] = []
        while queue:
            nid = queue.pop(0)
            order.append(nid)
            for succ in self._adj.get(nid, []):
                if succ in in_degree:
                    in_degree[succ] -= 1
                    if in_degree[succ] == 0:
                        queue.append(succ)
        return order

    # ── Hybrid mode ───────────────────────────────────────────────────────────

    _TRIGGER_TYPES  = {'manual_trigger', 'motion_filter', 'yolo_filter',
                       'time_interval_filter', 'time_of_day_filter'}
    _LOCAL_INF      = {'ollama_inference'}
    _CLOUD_INF      = {'claude_inference', 'gemini_inference', 'custom_prompt'}

    def _detect_hybrid_pairs(self) -> dict[str, str]:
        """
        Returns {local_node_id: cloud_node_id} for each pair of inference nodes
        that share the same trigger-type parent (hybrid mode).
        """
        from core.nodes.base import BaseNode

        # Build reverse-adjacency: node_id → set of parent ids
        rev: dict[str, set[str]] = {nid: set() for nid in self._node_map}
        for edge in self._graph_def.edges:
            rev[edge.target].add(edge.source)

        # Group inference nodes by their trigger parent
        trigger_to_local:  dict[str, list[str]] = {}
        trigger_to_cloud:  dict[str, list[str]] = {}
        for nid, node in self._node_map.items():
            if not isinstance(node, BaseNode) or node.META.category != 'inference':
                continue
            nt = node.META.node_type
            for parent_id in rev.get(nid, set()):
                parent = self._node_map.get(parent_id)
                if parent and hasattr(parent, 'META') and parent.META.node_type in self._TRIGGER_TYPES:
                    if nt in self._LOCAL_INF:
                        trigger_to_local.setdefault(parent_id, []).append(nid)
                    elif nt in self._CLOUD_INF:
                        trigger_to_cloud.setdefault(parent_id, []).append(nid)

        pairs: dict[str, str] = {}
        for trigger_id in trigger_to_local:
            if trigger_id in trigger_to_cloud:
                for local_id in trigger_to_local[trigger_id]:
                    for cloud_id in trigger_to_cloud[trigger_id]:
                        pairs[local_id] = cloud_id
        return pairs

    def _reorder_for_hybrid(self, order: list[str]) -> list[str]:
        """Ensure local inference always precedes its cloud fallback in topo order."""
        order = list(order)
        for local_id, cloud_id in self._hybrid_pairs.items():
            if local_id in order and cloud_id in order:
                li, ci = order.index(local_id), order.index(cloud_id)
                if ci < li:
                    order[li], order[ci] = order[ci], order[li]
        return order

    # ── Static helpers ────────────────────────────────────────────────────────

    @staticmethod
    def _node_meta_vram(nd: "NodeDef") -> int:
        """Return vram_mb for a node definition without instantiating it."""
        from core.nodes.registry import NodeRegistry
        try:
            return NodeRegistry.get(nd.type).META.vram_mb
        except KeyError:
            return 0

    # ── Config validation (3.6) ───────────────────────────────────────────────

    @classmethod
    def validate(cls, graph_def: "GraphDefinition") -> list[str]:
        """
        Validate all node configs against their declared JSON Schemas.
        Returns a list of error strings (empty = valid).
        Does NOT instantiate nodes — safe to call before deploy.
        """
        from core.nodes.registry import NodeRegistry
        errors: list[str] = []
        try:
            import jsonschema
        except ImportError:
            return []  # jsonschema not installed — skip validation
        for nd in graph_def.nodes:
            try:
                klass = NodeRegistry.get(nd.type)
            except KeyError as e:
                errors.append(str(e))
                continue
            schema = klass.META.config_schema
            if not schema:
                continue
            try:
                jsonschema.validate(nd.config, schema)
            except jsonschema.ValidationError as e:
                errors.append(f"Node '{nd.id}' ({nd.type}): {e.message}")
        return errors

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    async def _setup_all(self) -> None:
        from core.nodes.base import BaseNode
        for node in self._node_map.values():
            if isinstance(node, BaseNode):
                await node.setup()

    async def _teardown_all(self) -> None:
        from core.nodes.base import BaseNode
        for node in self._node_map.values():
            if isinstance(node, BaseNode):
                await node.teardown()

    # ── Frame execution ───────────────────────────────────────────────────────

    async def _execute_frame(self, frame: "Frame") -> None:
        """Run frame through all processing nodes in topo order. Any None drops the frame."""
        from core.nodes.base import BaseNode
        current = frame
        inference_started = False
        skip: set[str] = set()
        try:
            for nid in self._topo_order:
                if nid in skip:
                    continue
                node = self._node_map[nid]
                if not isinstance(node, BaseNode):
                    continue
                if not inference_started and node.META.category == "inference":
                    inference_started = True
                    self.is_inferring = True
                    self.last_capture_id = current.capture_id

                cloud_fallback = self._hybrid_pairs.get(nid)  # non-None → nid is local in a hybrid pair
                try:
                    result = await node.process(current)
                except Exception:
                    if cloud_fallback:
                        log.warning(
                            "[hybrid] local node %s failed — falling back to %s",
                            node.META.node_type, self._node_map[cloud_fallback].META.node_type,
                        )
                        # current stays unchanged; cloud_fallback will run next
                        continue
                    log.exception("[graph] node %s (%s) raised — dropping frame", nid, node.META.node_type)
                    return

                if result is None:
                    return  # frame dropped (filter said no)

                if cloud_fallback:
                    # Local succeeded — skip the cloud fallback
                    skip.add(cloud_fallback)
                    log.debug("[hybrid] local %s succeeded — skipping cloud fallback", node.META.node_type)

                current = result
        finally:
            if inference_started:
                self.is_inferring = False

    async def trigger_now(self) -> bool:
        """Grab the current frame and run the full graph immediately."""
        raw = self._source.latest_frame()
        if raw is None:
            return False
        # Override capture_id so UI can track this manual trigger
        frame = raw.__class__(
            image=raw.image,
            source_id=raw.source_id,
            capture_id=str(uuid.uuid4()),
            timestamp=raw.timestamp,
            metadata={**raw.metadata, "trigger": "manual", "_manual_trigger": True},
        )
        self.last_capture_id = frame.capture_id
        self.is_inferring = True
        try:
            await self._execute_frame(frame)
        finally:
            self.is_inferring = False
        return True

    # ── Main loop ─────────────────────────────────────────────────────────────

    async def run(self) -> None:
        self._source.start()
        await self._setup_all()
        node_types = [n.META.node_type for n in self._node_map.values()]
        log.info("[graph] started — zone=%s nodes=%s", self._ctx.zone.name, node_types)
        last_processed_ts: float = 0.0
        try:
            while True:
                frame = self._source.latest_frame()
                if frame is not None and frame.timestamp > last_processed_ts:
                    last_processed_ts = frame.timestamp
                    await self._execute_frame(frame)
                else:
                    log.debug("[graph] no new frame")
                await asyncio.sleep(0.1)
        except asyncio.CancelledError:
            log.info("[graph] stopping — zone=%s", self._ctx.zone.name)
        finally:
            self._source.stop()
            await self._teardown_all()


from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from core.frame import Frame
