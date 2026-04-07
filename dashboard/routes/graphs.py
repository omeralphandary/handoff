"""Graph API — CRUD, deploy/stop, catalog, telemetry, import/export."""
from __future__ import annotations
import asyncio
import json
import uuid
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse
import core.nodes  # registers all node types
from core.graph import GraphDefinition, GraphExecutor, ExecutionContext
from core.templates import default_graph_from_zone
from core.zone import Zone
import config

router = APIRouter(prefix="/graphs", tags=["graphs"])


# ── 4.1  Graph CRUD ─────────────────────────────────────────────────────────

@router.get("")
async def list_graphs(request: Request):
    """List all graphs (currently derived from zones)."""
    store = request.app.state.store
    zones = await store.list_zones()
    result = []
    for z in zones:
        active = z["id"] in request.app.state.active_dispatchers
        executor = request.app.state.zone_dispatchers.get(z["id"])
        result.append({
            "id":        z["id"],
            "name":      z["name"],
            "active":    active,
            "vram_mb":   getattr(executor, "vram_required_mb", None),
        })
    return JSONResponse(result)


@router.get("/{graph_id}")
async def get_graph(graph_id: str, request: Request):
    """Return the GraphDefinition for a zone."""
    store = request.app.state.store
    zone_dict = await store.get_zone(graph_id)
    if not zone_dict:
        raise HTTPException(404, f"Graph {graph_id!r} not found")
    zone = _zone_from_dict(zone_dict)
    raw_graph = zone_dict.get("graph_json")
    if raw_graph:
        graph_def = GraphDefinition.from_dict(json.loads(raw_graph))
    else:
        graph_def = default_graph_from_zone(zone)
        # Overlay saved canvas positions onto node configs (legacy path)
        for nd in graph_def.nodes:
            pos = zone.node_positions.get(nd.id)
            if pos:
                nd.config["_x"] = pos["x"]
                nd.config["_y"] = pos["y"]
    return JSONResponse({
        "id":   graph_id,
        "name": zone_dict["name"],
        "graph": graph_def.to_dict(),
        "vram_required_mb": sum(
            GraphExecutor._node_meta_vram(nd) for nd in graph_def.nodes
        ),
    })


@router.put("/{graph_id}")
async def update_graph(graph_id: str, request: Request):
    """
    Persist edited graph back to the zone store.
    Extracts zone-level fields from the source node config and trigger node config,
    then updates the zone row so changes survive restart.
    """
    import json as _json
    store = request.app.state.store
    body = await request.json()
    graph_def = GraphDefinition.from_dict(body.get("graph", body))

    errors = GraphExecutor.validate(graph_def)
    if errors:
        raise HTTPException(422, {"errors": errors})

    zone_dict = await store.get_zone(graph_id)
    if not zone_dict:
        raise HTTPException(404)

    # Extract fields from nodes back to zone model
    updates: dict = {}
    task_types: list[str] = []

    for nd in graph_def.nodes:
        if nd.type == "camera_source":
            if nd.config.get("url"):
                updates["camera_url"] = nd.config["url"]

        elif nd.type == "crop_filter":
            updates["polygon"] = nd.config.get("polygon", [])

        elif nd.type == "trigger":
            _rev = {"interval": "sequence", "by_class": "by_class",
                    "motion": "motion", "manual": "manual"}
            updates["trigger_mode"] = _rev.get(nd.config.get("mode", "manual"), "manual")
            if "threshold_pct"    in nd.config: updates["motion_threshold"]  = nd.config["threshold_pct"]
            if "cooldown_seconds" in nd.config: updates["cooldown_seconds"]  = nd.config["cooldown_seconds"]
            if "interval_seconds" in nd.config: updates["sequence_interval"] = nd.config["interval_seconds"]
            if "classes"          in nd.config: updates["trigger_classes"]   = nd.config["classes"]

        elif nd.type == "manual_trigger":
            updates["trigger_mode"] = "manual"

        elif nd.type == "motion_filter":
            updates["trigger_mode"] = "motion"
            if "threshold_pct" in nd.config:
                updates["motion_threshold"] = nd.config["threshold_pct"]
            if "cooldown_seconds" in nd.config:
                updates["cooldown_seconds"] = nd.config["cooldown_seconds"]

        elif nd.type == "time_interval_filter":
            updates["trigger_mode"] = "sequence"
            if "interval_seconds" in nd.config:
                updates["sequence_interval"] = nd.config["interval_seconds"]

        elif nd.type == "yolo_filter":
            updates["trigger_mode"] = "by_class"
            if "classes" in nd.config:
                updates["trigger_classes"] = nd.config["classes"]
            if "cooldown_seconds" in nd.config:
                updates["cooldown_seconds"] = nd.config["cooldown_seconds"]

        elif nd.type in ("claude_inference", "ollama_inference", "gemini_inference", "custom_prompt"):
            t = nd.config.get("task_type") or nd.config.get("task_label")
            if t and t not in task_types:
                task_types.append(str(t))

    if task_types:
        updates["task_types"] = task_types

    # Save full graph as canonical source (preserves extra nodes + positions)
    updates["graph_json"] = json.dumps(graph_def.to_dict())
    # Also keep node_positions for legacy fallback
    updates["node_positions"] = {
        nd.id: {"x": nd.config["_x"], "y": nd.config["_y"]}
        for nd in graph_def.nodes
        if isinstance(nd.config.get("_x"), (int, float)) and isinstance(nd.config.get("_y"), (int, float))
    }

    if updates:
        await store.update_zone(graph_id, **updates)

    # Hot-patch running executor if active
    executor = request.app.state.zone_dispatchers.get(graph_id)
    if executor:
        z = executor._ctx.zone
        for k, v in updates.items():
            if hasattr(z, k):
                setattr(z, k, v)

    running = graph_id in request.app.state.active_dispatchers
    return JSONResponse({
        "status": "updated",
        "persisted_fields": list(updates.keys()),
        "restart_required": running,
        "message": "Restart the graph to apply pipeline structure changes." if running else "Saved.",
    })


@router.delete("/{graph_id}")
async def delete_graph(graph_id: str, request: Request):
    store = request.app.state.store
    # Stop if running
    _stop_executor(graph_id, request)
    deleted = await store.delete_zone(graph_id)
    if not deleted:
        raise HTTPException(404)
    return JSONResponse({"status": "deleted"})


# ── 4.2  Deploy / lifecycle ──────────────────────────────────────────────────

@router.post("/{graph_id}/deploy")
async def deploy_graph(graph_id: str, request: Request):
    store = request.app.state.store
    if graph_id in request.app.state.active_dispatchers:
        return JSONResponse({"status": "already_running"})

    zone_dict = await store.get_zone(graph_id)
    if not zone_dict:
        raise HTTPException(404)

    zone = _zone_from_dict(zone_dict)
    graph_def = default_graph_from_zone(zone)

    errors = GraphExecutor.validate(graph_def)
    if errors:
        raise HTTPException(422, {"errors": errors})

    ctx = ExecutionContext(zone=zone, store=store)
    executor = GraphExecutor(graph_def, ctx)
    task = asyncio.create_task(executor.run(), name=f"zone-{graph_id}")
    request.app.state.active_dispatchers[graph_id] = task
    request.app.state.zone_dispatchers[graph_id] = executor
    await store.set_zone_active(graph_id, True)

    return JSONResponse({
        "status":    "deployed",
        "vram_mb":   executor.vram_required_mb,
        "nodes":     len(executor._node_map),
    })


@router.post("/{graph_id}/stop")
async def stop_graph(graph_id: str, request: Request):
    store = request.app.state.store
    stopped = _stop_executor(graph_id, request)
    if stopped:
        await store.set_zone_active(graph_id, False)
    return JSONResponse({"status": "stopped" if stopped else "not_running"})


@router.post("/{graph_id}/restart")
async def restart_graph(graph_id: str, request: Request):
    _stop_executor(graph_id, request)
    await asyncio.sleep(0.1)  # let cancel propagate
    return await deploy_graph(graph_id, request)


@router.get("/{graph_id}/status")
async def graph_status(graph_id: str, request: Request):
    executor = request.app.state.zone_dispatchers.get(graph_id)
    active = graph_id in request.app.state.active_dispatchers
    if not executor or not active:
        return JSONResponse({"active": False, "inferring": False, "vram_mb": 0})
    return JSONResponse({
        "active":          True,
        "inferring":       executor.is_inferring,
        "last_capture_id": executor.last_capture_id,
        "vram_mb":         getattr(executor, "vram_required_mb", 0),
    })


# ── 4.3  Node catalog ────────────────────────────────────────────────────────

@router.get("/catalog/nodes")
async def node_catalog():
    """All registered node types with metadata + config schema."""
    from core.nodes.registry import NodeRegistry
    return JSONResponse(NodeRegistry.catalog())


@router.get("/catalog/nodes/{node_type}")
async def node_schema(node_type: str):
    from core.nodes.registry import NodeRegistry
    try:
        klass = NodeRegistry.get(node_type)
    except KeyError:
        raise HTTPException(404, f"Unknown node type: {node_type!r}")
    m = klass.META
    return JSONResponse({
        "type":          m.node_type,
        "label":         m.label,
        "category":      m.category,
        "icon":          m.icon,
        "vram_mb":       m.vram_mb,
        "config_schema": m.config_schema,
    })


# ── 4.4  Live telemetry (SSE) ────────────────────────────────────────────────

@router.get("/{graph_id}/telemetry")
async def graph_telemetry(graph_id: str, request: Request):
    """Server-Sent Events stream of live executor state."""
    async def _generate():
        while True:
            if await request.is_disconnected():
                break
            executor = request.app.state.zone_dispatchers.get(graph_id)
            active = graph_id in request.app.state.active_dispatchers
            data = json.dumps({
                "active":          bool(active and executor),
                "inferring":       executor.is_inferring if executor else False,
                "last_capture_id": executor.last_capture_id if executor else None,
                "vram_mb":         getattr(executor, "vram_required_mb", 0) if executor else 0,
            })
            yield f"data: {data}\n\n"
            await asyncio.sleep(1.0)

    return StreamingResponse(_generate(), media_type="text/event-stream")


# ── 4.5  Import / export ─────────────────────────────────────────────────────

@router.get("/{graph_id}/export")
async def export_graph(graph_id: str, request: Request):
    """Download the graph definition as a JSON file."""
    store = request.app.state.store
    zone_dict = await store.get_zone(graph_id)
    if not zone_dict:
        raise HTTPException(404)
    zone = _zone_from_dict(zone_dict)
    graph_def = default_graph_from_zone(zone)
    filename = f"oversight-graph-{zone_dict['name'].replace(' ', '_')}.json"
    payload = json.dumps({
        "name":  zone_dict["name"],
        "graph": graph_def.to_dict(),
    }, indent=2)
    return StreamingResponse(
        iter([payload]),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/import")
async def import_graph(request: Request):
    """
    Upload a graph JSON (exported from another deployment).
    Creates a new zone + graph. Does not auto-deploy.
    """
    store = request.app.state.store
    body = await request.json()
    graph_def = GraphDefinition.from_dict(body.get("graph", body))

    errors = GraphExecutor.validate(graph_def)
    if errors:
        raise HTTPException(422, {"errors": errors})

    # Extract camera URL from source node
    camera_url = ""
    for nd in graph_def.nodes:
        if nd.type == "camera_source":
            camera_url = nd.config.get("url", "")
            break

    zone = Zone(
        id=str(uuid.uuid4()),
        name=body.get("name", "Imported Graph"),
        camera_url=camera_url,
    )
    await store.create_zone(zone)
    return JSONResponse({"status": "imported", "id": zone.id}, status_code=201)


# ── 4.6  Manual trigger ──────────────────────────────────────────────────────

@router.post("/{graph_id}/trigger")
async def trigger_graph(graph_id: str, request: Request):
    executor = request.app.state.zone_dispatchers.get(graph_id)
    if not executor:
        raise HTTPException(404, "Graph not running — deploy it first")
    fired = await executor.trigger_now()
    return JSONResponse({"status": "triggered" if fired else "no_frame"})


# ── Helpers ──────────────────────────────────────────────────────────────────

def _zone_from_dict(d: dict) -> Zone:
    clean = {k: v for k, v in d.items() if k not in ("active", "task_type")}
    if "task_types" not in clean:
        clean["task_types"] = ["documentation"]
    if "trigger_mode" not in clean:
        clean["trigger_mode"] = "manual"
    if "trigger_classes" not in clean:
        clean["trigger_classes"] = []
    if "node_positions" not in clean:
        clean["node_positions"] = {}
    return Zone(**clean)


def _stop_executor(graph_id: str, request: Request) -> bool:
    dispatchers = request.app.state.active_dispatchers
    if graph_id not in dispatchers:
        return False
    dispatchers[graph_id].cancel()
    del dispatchers[graph_id]
    request.app.state.zone_dispatchers.pop(graph_id, None)
    return True
