"""Mock authentication routes — demo only, not production auth."""
from __future__ import annotations
import secrets
from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
import config

router = APIRouter(tags=["auth"])
templates = Jinja2Templates(directory=str(config.BASE_DIR / "dashboard" / "templates"))

# In-memory session store — process-local, cleared on restart (intentional for demo)
_sessions: dict[str, str] = {}  # token → username


def is_authenticated(request: Request) -> bool:
    token = request.cookies.get("hf_session")
    return token is not None and token in _sessions


@router.get("/login", response_class=HTMLResponse, include_in_schema=False)
async def login_page(request: Request, next: str = "/"):
    if is_authenticated(request):
        return RedirectResponse(next or "/", status_code=303)
    return templates.TemplateResponse(request, "login.html", {"next": next, "error": None})


@router.post("/login", include_in_schema=False)
async def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    next: str = Form("/"),
):
    if username == config.DEMO_USERNAME and password == config.DEMO_PASSWORD:
        token = secrets.token_urlsafe(32)
        _sessions[token] = username
        redirect_to = next if next.startswith("/") else "/"
        response = RedirectResponse(redirect_to, status_code=303)
        response.set_cookie(
            "hf_session", token,
            httponly=True, samesite="lax",
            max_age=8 * 3600,  # 8-hour session
        )
        return response
    return templates.TemplateResponse(
        request,
        "login.html",
        {"next": next, "error": "Invalid credentials"},
        status_code=401,
    )


@router.post("/logout", include_in_schema=False)
async def logout(request: Request):
    token = request.cookies.get("hf_session")
    if token:
        _sessions.pop(token, None)
    response = RedirectResponse("/login", status_code=303)
    response.delete_cookie("hf_session")
    return response
