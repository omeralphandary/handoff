"""FastAPI dashboard app."""
from __future__ import annotations
import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request

# Configure logging here so it works whether started via `python main.py`
# or directly via `uvicorn dashboard.main:app`.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("anthropic").setLevel(logging.WARNING)
logging.getLogger("apscheduler").setLevel(logging.WARNING)
logging.getLogger("multipart").setLevel(logging.WARNING)
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from storage.local import LocalStore
from dashboard.routes import zones, records, events, health, overview, settings as settings_router
from dashboard.routes import auth as auth_router
from dashboard.routes import graphs as graphs_router
import config

# Public paths that don't require authentication
_PUBLIC_PATHS = {"/login", "/logout", "/health"}
_PUBLIC_PREFIXES = ("/static",)

store = LocalStore()
scheduler = AsyncIOScheduler()
templates = Jinja2Templates(directory=str(config.BASE_DIR / "dashboard" / "templates"))


@asynccontextmanager
async def lifespan(app: FastAPI):
    await store.init()
    app.state.store = store
    app.state.active_dispatchers: dict = {}   # zone_id -> asyncio.Task
    app.state.zone_dispatchers: dict = {}     # zone_id -> ZoneDispatcher
    scheduler.add_job(store.purge_expired, "interval", hours=12)
    scheduler.add_job(
        lambda: asyncio.create_task(store.purge_old_pdfs(config.PDF_RETENTION_HOURS)),
        "interval", hours=1,
    )
    scheduler.start()
    yield
    # Cancel all running zone dispatchers on shutdown
    for task in app.state.active_dispatchers.values():
        task.cancel()
    await asyncio.gather(*app.state.active_dispatchers.values(), return_exceptions=True)
    for dispatcher in app.state.zone_dispatchers.values():
        dispatcher._stream.stop()
    scheduler.shutdown()


app = FastAPI(title="Oversight", lifespan=lifespan)
app.mount("/static/images", StaticFiles(directory=str(config.IMAGES_DIR)), name="images")

# Serve built React canvas (production)
_canvas_dir = config.BASE_DIR / "dashboard" / "static" / "app"
if _canvas_dir.exists():
    app.mount("/app", StaticFiles(directory=str(_canvas_dir), html=True), name="canvas")

# CORS for local frontend dev (npm run dev on :3000)
import os as _os
if _os.getenv("ENV", "production") == "development":
    from fastapi.middleware.cors import CORSMiddleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


@app.middleware("http")
async def auth_guard(request: Request, call_next):
    """Redirect unauthenticated requests to /login."""
    path = request.url.path
    is_public = path in _PUBLIC_PATHS or any(path.startswith(p) for p in _PUBLIC_PREFIXES)
    if not is_public:
        from dashboard.routes.auth import is_authenticated
        if not is_authenticated(request):
            return RedirectResponse(f"/login?next={path}", status_code=303)
    return await call_next(request)


@app.middleware("http")
async def sidebar_context(request: Request, call_next):
    """Inject sidebar zones into every request so base.html can render the nav."""
    try:
        if hasattr(request.app.state, "store"):
            request.state.sidebar_zones = await request.app.state.store.list_zones()
        else:
            request.state.sidebar_zones = []
    except Exception:
        request.state.sidebar_zones = []
    return await call_next(request)


app.include_router(auth_router.router)
app.include_router(graphs_router.router)
app.include_router(overview.router)
app.include_router(zones.router)
app.include_router(records.router)
app.include_router(events.router)
app.include_router(health.router)
app.include_router(settings_router.router)


@app.get("/", include_in_schema=False)
async def root():
    return RedirectResponse("/overview")
