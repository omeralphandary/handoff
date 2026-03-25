"""Evidence log routes."""
from __future__ import annotations
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, FileResponse

router = APIRouter(prefix="/evidence", tags=["evidence"])


@router.get("/", response_class=HTMLResponse)
async def list_evidence(request: Request):
    # TODO: return evidence template with records
    return HTMLResponse("<h1>Evidence — coming soon</h1>")


@router.get("/{record_id}/pdf")
async def download_pdf(record_id: str):
    # TODO: look up record, return pdf
    return HTMLResponse("<h1>PDF download — coming soon</h1>")
