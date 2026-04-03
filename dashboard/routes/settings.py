"""System settings route."""
from __future__ import annotations
from pathlib import Path
from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from typing import Annotated
import config

router = APIRouter(prefix="/settings", tags=["settings"])
templates = Jinja2Templates(directory=str(config.BASE_DIR / "dashboard" / "templates"))

VALID_BACKENDS = {"local", "anthropic", "hybrid"}


@router.get("/", response_class=HTMLResponse)
async def settings_page(request: Request):
    return templates.TemplateResponse(
        request,
        "settings.html",
        {
            "vlm_backend": config.VLM_BACKEND,
            "vlm_model": config.VLM_MODEL,
            "local_model": config.LOCAL_MODEL,
            "ollama_url": config.OLLAMA_URL,
            "has_anthropic_key": bool(config.ANTHROPIC_API_KEY),
        },
    )


@router.post("/backend", response_class=RedirectResponse)
async def set_backend(request: Request, backend: Annotated[str, Form()]):
    if backend not in VALID_BACKENDS:
        return RedirectResponse("/settings", status_code=303)

    # Update runtime config
    config.VLM_BACKEND = backend

    # Persist to .env
    env_path = config.BASE_DIR / ".env"
    lines = env_path.read_text().splitlines()
    lines = [f"VLM_BACKEND={backend}" if l.startswith("VLM_BACKEND=") else l for l in lines]
    env_path.write_text("\n".join(lines) + "\n")

    # Swap VLM client on all active dispatchers in-place
    from vlm.client import get_vlm_client
    new_vlm = get_vlm_client()
    for dispatcher in request.app.state.zone_dispatchers.values():
        for task in dispatcher.tasks:
            if hasattr(task, "vlm"):
                task.vlm = new_vlm

    import logging
    logging.getLogger("settings").info("[settings] VLM backend switched to %s", backend)
    return RedirectResponse("/settings", status_code=303)
