"""Zone management routes."""
from __future__ import annotations
import asyncio
import uuid
from typing import Annotated
from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from core.zone import Zone
import core.nodes  # registers all node types
from core.graph import GraphExecutor, ExecutionContext
from core.templates import default_graph_from_zone
import config

router = APIRouter(prefix="/zones", tags=["zones"])
templates = Jinja2Templates(directory=str(config.BASE_DIR / "dashboard" / "templates"))

TASK_TYPES = ["documentation", "ocr", "classification"]
from core.yolo_gate import AVAILABLE_CLASSES


@router.get("/", response_class=HTMLResponse)
async def list_zones(request: Request):
    store = request.app.state.store
    zones = await store.list_zones()
    active_ids = set(request.app.state.active_dispatchers.keys())
    return templates.TemplateResponse(
        request,
        "zones.html",
        {"zones": zones, "active_ids": active_ids, "task_types": TASK_TYPES, "trigger_classes": AVAILABLE_CLASSES},
    )


@router.get("/new", response_class=HTMLResponse)
async def new_zone_form(request: Request):
    return templates.TemplateResponse(
        request,
        "zone_new.html",
        {"task_types": TASK_TYPES, "trigger_classes": AVAILABLE_CLASSES},
    )


@router.get("/{zone_id}", response_class=HTMLResponse)
async def zone_detail(zone_id: str, request: Request):
    store = request.app.state.store
    zone = await store.get_zone(zone_id)
    if not zone:
        return RedirectResponse("/zones", status_code=303)
    captures = await store.list_captures(zone_id=zone_id, limit=50)
    flagged = [c for c in captures if c["flagged"]]
    from urllib.parse import urlparse
    parsed = urlparse(zone["camera_url"])
    camera_host = parsed.hostname or ""
    # Fetch live camera settings via HTTP API (non-fatal)
    import logging as _log
    imaging = None
    from core.reolink import get_camera_settings
    loop = asyncio.get_event_loop()
    try:
        imaging = await asyncio.wait_for(
            loop.run_in_executor(None, lambda: get_camera_settings(zone["camera_url"])),
            timeout=5.0,
        )
    except Exception as e:
        _log.getLogger("dashboard").warning("[camera settings] failed to fetch: %s", e)
    return templates.TemplateResponse(
        request,
        "zone_detail.html",
        {
            "zone": zone,
            "captures": captures,
            "flagged": flagged,
            "camera_host": camera_host,
            "imaging": imaging,
        },
    )


@router.get("/{zone_id}/edit", response_class=HTMLResponse)
async def edit_zone_form(zone_id: str, request: Request):
    store = request.app.state.store
    zone = await store.get_zone(zone_id)
    if not zone:
        return RedirectResponse("/zones", status_code=303)
    return templates.TemplateResponse(
        request,
        "zone_edit.html",
        {"zone": zone, "task_types": TASK_TYPES, "trigger_classes": AVAILABLE_CLASSES},
    )


@router.post("/{zone_id}/edit", response_class=RedirectResponse)
async def edit_zone(
    zone_id: str,
    request: Request,
    name: str = Form(...),
    camera_url: str = Form(...),
    task_types: Annotated[list[str], Form()] = ["documentation"],
    trigger_mode: str = Form("motion"),
    trigger_classes: Annotated[list[str], Form()] = [],
    retention_days: int = Form(90),
    cooldown_seconds: float = Form(10.0),
    motion_threshold: float = Form(0.02),
    sequence_interval: float = Form(0.0),
    polygon: str = Form("[]"),
):
    import json as _json
    store = request.app.state.store
    try:
        polygon_data = _json.loads(polygon)
    except Exception:
        polygon_data = []
    await store.update_zone(
        zone_id,
        name=name,
        camera_url=camera_url,
        task_types=task_types or ["documentation"],
        trigger_mode=trigger_mode,
        trigger_classes=trigger_classes,
        retention_days=retention_days,
        cooldown_seconds=cooldown_seconds,
        motion_threshold=motion_threshold,
        sequence_interval=sequence_interval,
        polygon=polygon_data,
    )
    # Patch live executor's context zone so running inference picks up changes immediately
    executor = request.app.state.zone_dispatchers.get(zone_id)
    if executor and isinstance(executor, GraphExecutor):
        z = executor._ctx.zone
        old_url = z.camera_url
        z.name = name
        z.camera_url = camera_url
        z.task_types = task_types or ["documentation"]
        z.trigger_mode = trigger_mode
        z.trigger_classes = trigger_classes
        z.retention_days = retention_days
        z.cooldown_seconds = cooldown_seconds
        z.motion_threshold = motion_threshold
        z.sequence_interval = sequence_interval
        z.polygon = polygon_data
        # Patch trigger node internals if it's still running
        from core.nodes.filters.motion import MotionFilterNode
        from core.nodes.filters.yolo import YOLOFilterNode
        from core.yolo_gate import YOLOGate
        for node in executor._node_map.values():
            if isinstance(node, MotionFilterNode):
                node._trigger.threshold_pct = motion_threshold
                node._trigger.cooldown_seconds = cooldown_seconds
            elif isinstance(node, YOLOFilterNode):
                node._gate = YOLOGate(trigger_classes) if trigger_classes else node._gate
                node._motion.cooldown_seconds = cooldown_seconds
        # If camera URL changed, reconnect the stream
        if camera_url != old_url:
            executor._stream._stream.url = camera_url
            executor._stream._stream.reconnect()
    return RedirectResponse(f"/zones/{zone_id}", status_code=303)


@router.post("/", response_class=RedirectResponse)
async def create_zone(
    request: Request,
    name: str = Form(...),
    camera_url: str = Form(...),
    task_types: Annotated[list[str], Form()] = ["documentation"],
    trigger_mode: str = Form("motion"),
    trigger_classes: Annotated[list[str], Form()] = [],
    retention_days: int = Form(90),
    cooldown_seconds: float = Form(10.0),
    motion_threshold: float = Form(0.02),
    sequence_interval: float = Form(0.0),
    polygon: str = Form("[]"),
):
    import json as _json
    store = request.app.state.store
    try:
        polygon_data = _json.loads(polygon)
    except Exception:
        polygon_data = []
    zone = Zone(
        id=str(uuid.uuid4()),
        name=name,
        camera_url=camera_url,
        task_types=task_types or ["documentation"],
        trigger_mode=trigger_mode,
        trigger_classes=trigger_classes,
        retention_days=retention_days,
        cooldown_seconds=cooldown_seconds,
        motion_threshold=motion_threshold,
        sequence_interval=sequence_interval,
        polygon=polygon_data,
    )
    await store.create_zone(zone)
    return RedirectResponse("/zones", status_code=303)


@router.post("/{zone_id}/delete", response_class=RedirectResponse)
async def delete_zone(zone_id: str, request: Request):
    store = request.app.state.store
    # Stop dispatcher if running
    dispatchers = request.app.state.active_dispatchers
    if zone_id in dispatchers:
        dispatchers[zone_id].cancel()
        request.app.state.zone_dispatchers.pop(zone_id, None)
        del dispatchers[zone_id]
    await store.delete_zone(zone_id)
    return RedirectResponse("/zones", status_code=303)


@router.post("/{zone_id}/start", response_class=RedirectResponse)
async def start_zone(zone_id: str, request: Request):
    store = request.app.state.store
    dispatchers = request.app.state.active_dispatchers
    if zone_id in dispatchers:
        return RedirectResponse(f"/zones/{zone_id}", status_code=303)

    zone_dict = await store.get_zone(zone_id)
    if not zone_dict:
        return RedirectResponse("/zones", status_code=303)

    d = {k: v for k, v in zone_dict.items() if k not in ("active", "task_type")}
    if "task_types" not in d:
        d["task_types"] = zone_dict.get("task_types") or zone_dict.get("task_type") or ["documentation"]
    if "trigger_mode" not in d:
        d["trigger_mode"] = "manual"
    if "trigger_classes" not in d:
        d["trigger_classes"] = []
    zone = Zone(**d)
    ctx = ExecutionContext(zone=zone, store=store)
    graph_def = default_graph_from_zone(zone)
    executor = GraphExecutor(graph_def, ctx)

    task = asyncio.create_task(executor.run(), name=f"zone-{zone_id}")
    dispatchers[zone_id] = task
    request.app.state.zone_dispatchers[zone_id] = executor
    await store.set_zone_active(zone_id, True)
    return RedirectResponse(f"/zones/{zone_id}", status_code=303)


@router.post("/{zone_id}/stop", response_class=RedirectResponse)
async def stop_zone(zone_id: str, request: Request):
    store = request.app.state.store
    dispatchers = request.app.state.active_dispatchers
    if zone_id in dispatchers:
        dispatchers[zone_id].cancel()
        try:
            await dispatchers[zone_id]
        except asyncio.CancelledError:
            pass
        del dispatchers[zone_id]
        request.app.state.zone_dispatchers.pop(zone_id, None)
    await store.set_zone_active(zone_id, False)
    return RedirectResponse(f"/zones/{zone_id}", status_code=303)


@router.post("/{zone_id}/imaging", response_class=RedirectResponse)
async def set_imaging(
    zone_id: str, request: Request,
    brightness: Annotated[int, Form()] = 128,
    contrast: Annotated[int, Form()] = 128,
    hue: Annotated[int, Form()] = 128,
    saturation: Annotated[int, Form()] = 128,
    sharpness: Annotated[int, Form()] = 128,
):
    store = request.app.state.store
    zone = await store.get_zone(zone_id)
    if zone:
        from core.reolink import set_image
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, lambda: set_image(
            zone["camera_url"], brightness, contrast, hue, saturation, sharpness,
        ))
    return RedirectResponse(f"/zones/{zone_id}", status_code=303)


@router.post("/{zone_id}/ir", response_class=RedirectResponse)
async def set_ir_route(zone_id: str, request: Request, state: Annotated[str, Form()]):
    store = request.app.state.store
    zone = await store.get_zone(zone_id)
    if zone:
        from core.reolink import set_ir
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, lambda: set_ir(zone["camera_url"], state))
    return RedirectResponse(f"/zones/{zone_id}", status_code=303)


@router.post("/{zone_id}/led", response_class=RedirectResponse)
async def set_led_route(
    zone_id: str, request: Request,
    state: Annotated[int, Form()] = 0,
    bright: Annotated[int, Form()] = 50,
):
    store = request.app.state.store
    zone = await store.get_zone(zone_id)
    if zone:
        from core.reolink import set_white_led
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, lambda: set_white_led(zone["camera_url"], state, bright))
    return RedirectResponse(f"/zones/{zone_id}", status_code=303)


@router.post("/{zone_id}/reconnect", response_class=RedirectResponse)
async def reconnect_zone(zone_id: str, request: Request):
    dispatcher = request.app.state.zone_dispatchers.get(zone_id)
    if dispatcher:
        dispatcher._stream.reconnect()
    return RedirectResponse(f"/zones/{zone_id}", status_code=303)


@router.get("/{zone_id}/status")
async def zone_status(zone_id: str, request: Request):
    from fastapi.responses import JSONResponse
    executor = request.app.state.zone_dispatchers.get(zone_id)
    if not executor:
        return JSONResponse({"active": False, "inferring": False, "last_capture_id": None, "vram_mb": 0})
    return JSONResponse({
        "active": True,
        "inferring": executor.is_inferring,
        "last_capture_id": executor.last_capture_id,
        "vram_mb": getattr(executor, "vram_required_mb", 0),
    })


@router.post("/{zone_id}/trigger", response_class=RedirectResponse)
async def trigger_zone(zone_id: str, request: Request):
    dispatcher = request.app.state.zone_dispatchers.get(zone_id)
    if not dispatcher:
        return RedirectResponse(f"/zones/{zone_id}", status_code=303)
    await dispatcher.trigger_now()
    return RedirectResponse(f"/zones/{zone_id}", status_code=303)


@router.post("/preview-frame")
async def preview_frame(request: Request, camera_url: str = Form(...)):
    """Grab a single frame from a camera URL for polygon setup — no dispatcher needed."""
    from urllib.parse import urlparse as _urlparse
    from fastapi.responses import Response
    # SSRF guard — only allow RTSP streams
    _scheme = _urlparse(camera_url).scheme.lower()
    if _scheme not in ("rtsp", "rtsps"):
        return HTMLResponse("Only rtsp:// URLs are allowed", status_code=400)

    loop = asyncio.get_event_loop()
    def _grab():
        cmd = [
            "ffmpeg", "-loglevel", "error",
            "-rtsp_transport", "tcp",
            "-timeout", "10000000",
            "-probesize", "32",
            "-analyzeduration", "0",
            "-fflags", "+discardcorrupt+nobuffer",
            "-i", camera_url,
            "-vf", "scale='min(1920,iw)':-2",
            "-frames:v", "1",
            "-f", "image2", "-vcodec", "mjpeg",
            "pipe:1",
        ]
        import subprocess as _sp
        r = _sp.run(cmd, capture_output=True, timeout=20)
        return r.stdout if r.returncode == 0 else None
    try:
        data = await asyncio.wait_for(loop.run_in_executor(None, _grab), timeout=22)
    except Exception:
        data = None
    if not data:
        return HTMLResponse("", status_code=404)
    return Response(data, media_type="image/jpeg")


@router.get("/{zone_id}/snapshot")
async def snapshot(zone_id: str, request: Request):
    import cv2
    from fastapi.responses import Response
    dispatcher = request.app.state.zone_dispatchers.get(zone_id)
    if not dispatcher:
        return HTMLResponse("", status_code=404)
    frame_obj = dispatcher._stream.latest_frame()
    if frame_obj is None:
        return HTMLResponse("", status_code=404)
    # latest_frame() returns Frame (node arch) or ndarray (legacy dispatcher)
    img = frame_obj.image if hasattr(frame_obj, "image") else frame_obj
    _, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 85])
    return Response(buf.tobytes(), media_type="image/jpeg")


@router.get("/{zone_id}/stream")
async def mjpeg_stream(zone_id: str, request: Request):
    dispatcher = request.app.state.zone_dispatchers.get(zone_id)
    if not dispatcher:
        return HTMLResponse("<h3>Zone not active — start it first.</h3>", status_code=404)

    import cv2

    async def generate():
        last_frame_time = 0.0
        while True:
            if await request.is_disconnected():
                break
            try:
                d = request.app.state.zone_dispatchers.get(zone_id)
                if d is None:
                    break
                ft = d._stream.last_frame_time
                if ft > last_frame_time:
                    frame_obj = d._stream.latest_frame()
                    if frame_obj is not None:
                        img = frame_obj.image if hasattr(frame_obj, "image") else frame_obj
                        _, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 75])
                        yield (
                            b"--frame\r\nContent-Type: image/jpeg\r\n\r\n"
                            + buf.tobytes() + b"\r\n"
                        )
                        last_frame_time = ft
            except Exception:
                pass
            await asyncio.sleep(0.05)

    return StreamingResponse(
        generate(),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )
