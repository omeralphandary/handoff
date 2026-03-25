"""FastAPI dashboard app."""
from __future__ import annotations
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from storage.local import LocalStore
from dashboard.routes import zones, evidence
import config

store = LocalStore()
scheduler = AsyncIOScheduler()
templates = Jinja2Templates(directory=str(config.BASE_DIR / "dashboard" / "templates"))


@asynccontextmanager
async def lifespan(app: FastAPI):
    await store.init()
    scheduler.add_job(store.purge_expired, "interval", hours=12)
    scheduler.start()
    yield
    scheduler.shutdown()


app = FastAPI(title="Handoff", lifespan=lifespan)
app.include_router(zones.router)
app.include_router(evidence.router)
