"""Zone management routes."""
from __future__ import annotations
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

router = APIRouter(prefix="/zones", tags=["zones"])


@router.get("/", response_class=HTMLResponse)
async def list_zones(request: Request):
    # TODO: return zones template
    return HTMLResponse("<h1>Zones — coming soon</h1>")


@router.post("/")
async def create_zone(payload: dict):
    # TODO: persist zone, start ZoneDispatcher
    return {"status": "not implemented"}
