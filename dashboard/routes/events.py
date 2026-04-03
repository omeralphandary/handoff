"""Events routes — flagged captures that need attention."""
from __future__ import annotations
import math
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import config

router = APIRouter(prefix="/events", tags=["events"])
templates = Jinja2Templates(directory=str(config.BASE_DIR / "dashboard" / "templates"))

PAGE_SIZE = 50


@router.get("/", response_class=HTMLResponse)
async def list_events(request: Request):
    store = request.app.state.store
    zone_id = request.query_params.get("zone_id") or None
    page = max(1, int(request.query_params.get("page", 1)))
    offset = (page - 1) * PAGE_SIZE

    total = await store.count(zone_id=zone_id, flagged=True)
    events = await store.list(zone_id=zone_id, flagged=True, limit=PAGE_SIZE, offset=offset)
    zones = await store.list_zones()
    total_pages = max(1, math.ceil(total / PAGE_SIZE))

    return templates.TemplateResponse(
        request,
        "events.html",
        {
            "events": events,
            "zones": zones,
            "selected_zone": zone_id,
            "page": page,
            "total_pages": total_pages,
            "total": total,
        },
    )
