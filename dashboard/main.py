"""FastAPI dashboard app."""
from __future__ import annotations
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from storage.local import LocalStore
from dashboard.routes import zones, records, events, health, overview, settings as settings_router
import config

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


app = FastAPI(title="Handoff", lifespan=lifespan)
app.mount("/static/images", StaticFiles(directory=str(config.IMAGES_DIR)), name="images")


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


app.include_router(overview.router)
app.include_router(zones.router)
app.include_router(records.router)
app.include_router(events.router)
app.include_router(health.router)
app.include_router(settings_router.router)


@app.get("/", include_in_schema=False)
async def root():
    return RedirectResponse("/overview")
