"""Evidence log routes."""
from __future__ import annotations
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.templating import Jinja2Templates
import config

router = APIRouter(prefix="/evidence", tags=["evidence"])
templates = Jinja2Templates(directory=str(config.BASE_DIR / "dashboard" / "templates"))


@router.get("/", response_class=HTMLResponse)
async def list_evidence(request: Request):
    store = request.app.state.store
    zone_id = request.query_params.get("zone_id") or None
    records = await store.list(zone_id=zone_id, limit=100)
    zones = await store.list_zones()
    return templates.TemplateResponse(
        request,
        "evidence.html",
        {
            "records": records,
            "zones": zones,
            "selected_zone": zone_id,
        },
    )


@router.get("/{record_id}/pdf")
async def download_pdf(record_id: str, request: Request):
    store = request.app.state.store
    record = await store.get(record_id)
    if not record or not record.get("pdf_path"):
        return HTMLResponse("<h3>PDF not available for this record.</h3>", status_code=404)
    return FileResponse(
        record["pdf_path"],
        media_type="application/pdf",
        filename=f"handoff_{record_id[:8]}.pdf",
    )
