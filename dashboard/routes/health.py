"""System health panel — VLM backend, disk, zone status."""
from __future__ import annotations
import shutil
import asyncio
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import httpx
import config

router = APIRouter(prefix="/health", tags=["health"])
templates = Jinja2Templates(directory=str(config.BASE_DIR / "dashboard" / "templates"))


async def _ping_vlm() -> dict:
    if config.VLM_BACKEND == "anthropic":
        has_key = bool(config.ANTHROPIC_API_KEY)
        return {
            "backend": "anthropic",
            "model": config.VLM_MODEL,
            "status": "configured" if has_key else "missing API key",
            "ok": has_key,
        }
    # Local — ping Ollama
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            r = await client.get(f"{config.OLLAMA_URL}/api/tags")
        models = [m["name"] for m in r.json().get("models", [])]
        target_loaded = any(config.LOCAL_MODEL in m for m in models)
        return {
            "backend": "local (ollama)",
            "model": config.LOCAL_MODEL,
            "status": "online" if target_loaded else f"online — model {config.LOCAL_MODEL!r} not pulled",
            "ok": target_loaded,
            "available_models": models,
        }
    except Exception as exc:
        return {
            "backend": "local (ollama)",
            "model": config.LOCAL_MODEL,
            "status": f"unreachable — {exc}",
            "ok": False,
        }


def _disk_info() -> dict:
    usage = shutil.disk_usage(config.DATA_DIR)
    used_gb = usage.used / 1e9
    total_gb = usage.total / 1e9
    free_gb = usage.free / 1e9
    pct = usage.used / usage.total * 100
    return {
        "used_gb": round(used_gb, 1),
        "free_gb": round(free_gb, 1),
        "total_gb": round(total_gb, 1),
        "pct": round(pct, 1),
        "ok": pct < 85,
    }


def _data_stats() -> dict:
    images = list(config.IMAGES_DIR.glob("*.jpg")) if config.IMAGES_DIR.exists() else []
    reports = list(config.REPORTS_DIR.glob("*.pdf")) if config.REPORTS_DIR.exists() else []
    baselines = list(config.BASELINES_DIR.glob("*.jpg")) if config.BASELINES_DIR.exists() else []
    images_mb = sum(f.stat().st_size for f in images) / 1e6
    reports_mb = sum(f.stat().st_size for f in reports) / 1e6
    return {
        "images_count": len(images),
        "images_mb": round(images_mb, 1),
        "reports_count": len(reports),
        "reports_mb": round(reports_mb, 1),
        "baselines_count": len(baselines),
    }


@router.get("/", response_class=HTMLResponse)
async def health_panel(request: Request):
    store = request.app.state.store
    vlm, zones = await asyncio.gather(_ping_vlm(), store.list_zones())
    disk = _disk_info()
    data = _data_stats()
    active_count = sum(1 for z in zones if z["active"])
    return templates.TemplateResponse(
        request,
        "health.html",
        {
            "vlm": vlm,
            "disk": disk,
            "data": data,
            "zones": zones,
            "active_count": active_count,
        },
    )
