"""Records routes — all captured frames with status."""
from __future__ import annotations
import math
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.templating import Jinja2Templates
import config

router = APIRouter(tags=["records"])
templates = Jinja2Templates(directory=str(config.BASE_DIR / "dashboard" / "templates"))

PAGE_SIZE = 50


@router.get("/records", response_class=HTMLResponse)
async def list_records(request: Request):
    store = request.app.state.store
    zone_id = request.query_params.get("zone_id") or None
    page = max(1, int(request.query_params.get("page", 1)))
    offset = (page - 1) * PAGE_SIZE

    captures = await store.list_captures(zone_id=zone_id, limit=PAGE_SIZE, offset=offset)
    zones = await store.list_zones()
    # total count approximation — count distinct captures
    all_captures = await store.list_captures(zone_id=zone_id, limit=10000, offset=0)
    total = len(all_captures)
    total_pages = max(1, math.ceil(total / PAGE_SIZE))

    return templates.TemplateResponse(
        request,
        "records.html",
        {
            "captures": captures,
            "zones": zones,
            "selected_zone": zone_id,
            "page": page,
            "total_pages": total_pages,
            "total": total,
        },
    )


@router.get("/captures/{capture_id}", response_class=HTMLResponse)
async def capture_detail(capture_id: str, request: Request):
    store = request.app.state.store
    records = await store.get_capture(capture_id)
    if not records:
        return HTMLResponse("<h3>Capture not found.</h3>", status_code=404)
    return templates.TemplateResponse(
        request,
        "capture_detail.html",
        {"capture_id": capture_id, "records": records},
    )


@router.get("/records/{record_id}", response_class=HTMLResponse)
async def record_detail(record_id: str, request: Request):
    store = request.app.state.store
    record = await store.get(record_id)
    if not record:
        return HTMLResponse("<h3>Record not found.</h3>", status_code=404)
    return templates.TemplateResponse(request, "record_detail.html", {"record": record})


@router.get("/records/{record_id}/pdf")
async def download_pdf(record_id: str, request: Request):
    store = request.app.state.store
    record = await store.get(record_id)
    if not record or not record.get("pdf_path"):
        return HTMLResponse("<h3>PDF not available for this record.</h3>", status_code=404)
    return FileResponse(
        record["pdf_path"],
        media_type="application/pdf",
        filename=f"oversight_{record_id[:8]}.pdf",
    )
