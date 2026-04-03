"""Overview / dashboard route."""
from __future__ import annotations
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import config

router = APIRouter(tags=["overview"])
templates = Jinja2Templates(directory=str(config.BASE_DIR / "dashboard" / "templates"))


@router.get("/overview", response_class=HTMLResponse)
async def overview(request: Request):
    store = request.app.state.store
    stats = await store.stats()
    zones = await store.list_zones()
    recent = await store.list(limit=8)
    active_ids = set(request.app.state.active_dispatchers.keys())
    return templates.TemplateResponse(
        request,
        "overview.html",
        {
            "stats": stats,
            "zones": zones,
            "recent": recent,
            "active_ids": active_ids,
        },
    )
