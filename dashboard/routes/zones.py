"""Zone management routes."""
from __future__ import annotations
import asyncio
import uuid
from typing import Annotated
from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from core.zone import Zone
from core.dispatcher import ZoneDispatcher
from tasks.factory import build_tasks
from vlm.client import get_vlm_client
import config

router = APIRouter(prefix="/zones", tags=["zones"])
templates = Jinja2Templates(directory=str(config.BASE_DIR / "dashboard" / "templates"))

TASK_TYPES = ["documentation", "ocr", "inspection", "classification"]


@router.get("/", response_class=HTMLResponse)
async def list_zones(request: Request):
    store = request.app.state.store
    zones = await store.list_zones()
    active_ids = set(request.app.state.active_dispatchers.keys())
    return templates.TemplateResponse(
        request,
        "zones.html",
        {"zones": zones, "active_ids": active_ids, "task_types": TASK_TYPES},
    )


@router.get("/new", response_class=HTMLResponse)
async def new_zone_form(request: Request):
    return templates.TemplateResponse(
        request,
        "zone_new.html",
        {"task_types": TASK_TYPES},
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
        {"zone": zone, "task_types": TASK_TYPES},
    )


@router.post("/{zone_id}/edit", response_class=RedirectResponse)
async def edit_zone(
    zone_id: str,
    request: Request,
    name: str = Form(...),
    camera_url: str = Form(...),
    task_types: Annotated[list[str], Form()] = ["documentation"],
    trigger_mode: str = Form("motion"),
    retention_days: int = Form(90),
    cooldown_seconds: float = Form(10.0),
    motion_threshold: float = Form(0.02),
    sequence_interval: float = Form(0.0),
):
    store = request.app.state.store
    await store.update_zone(
        zone_id,
        name=name,
        camera_url=camera_url,
        task_types=task_types or ["documentation"],
        trigger_mode=trigger_mode,
        retention_days=retention_days,
        cooldown_seconds=cooldown_seconds,
        motion_threshold=motion_threshold,
        sequence_interval=sequence_interval,
    )
    return RedirectResponse(f"/zones/{zone_id}", status_code=303)


@router.post("/", response_class=RedirectResponse)
async def create_zone(
    request: Request,
    name: str = Form(...),
    camera_url: str = Form(...),
    task_types: Annotated[list[str], Form()] = ["documentation"],
    trigger_mode: str = Form("motion"),
    retention_days: int = Form(90),
    cooldown_seconds: float = Form(10.0),
    motion_threshold: float = Form(0.02),
    sequence_interval: float = Form(0.0),
):
    store = request.app.state.store
    zone = Zone(
        id=str(uuid.uuid4()),
        name=name,
        camera_url=camera_url,
        task_types=task_types or ["documentation"],
        trigger_mode=trigger_mode,
        retention_days=retention_days,
        cooldown_seconds=cooldown_seconds,
        motion_threshold=motion_threshold,
        sequence_interval=sequence_interval,
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
        d["trigger_mode"] = "motion"
    zone = Zone(**d)
    vlm = get_vlm_client()
    tasks = build_tasks(zone.task_types, vlm, store)
    dispatcher = ZoneDispatcher(zone, tasks)

    task = asyncio.create_task(dispatcher.run(), name=f"zone-{zone_id}")
    dispatchers[zone_id] = task
    request.app.state.zone_dispatchers[zone_id] = dispatcher
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


@router.post("/{zone_id}/trigger", response_class=RedirectResponse)
async def trigger_zone(zone_id: str, request: Request):
    dispatcher = request.app.state.zone_dispatchers.get(zone_id)
    if not dispatcher:
        return RedirectResponse(f"/zones/{zone_id}", status_code=303)
    await dispatcher.trigger_now()
    return RedirectResponse(f"/zones/{zone_id}", status_code=303)


@router.get("/{zone_id}/stream")
async def mjpeg_stream(zone_id: str, request: Request):
    dispatcher = request.app.state.zone_dispatchers.get(zone_id)
    if not dispatcher:
        return HTMLResponse("<h3>Zone not active — start it first.</h3>", status_code=404)

    import cv2

    async def generate():
        while True:
            if await request.is_disconnected():
                break
            try:
                d = request.app.state.zone_dispatchers.get(zone_id)
                if d is None:
                    break
                frame = d._stream.latest_frame()
                if frame is not None:
                    _, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
                    yield (
                        b"--frame\r\nContent-Type: image/jpeg\r\n\r\n"
                        + buf.tobytes()
                        + b"\r\n"
                    )
            except Exception:
                pass
            await asyncio.sleep(0.1)

    return StreamingResponse(
        generate(),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )
