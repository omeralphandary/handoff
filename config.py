from __future__ import annotations
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
IMAGES_DIR = DATA_DIR / "images"
REPORTS_DIR = DATA_DIR / "reports"
DB_PATH = DATA_DIR / "handoff.db"

ANTHROPIC_API_KEY: str = os.environ["ANTHROPIC_API_KEY"]
VLM_MODEL: str = os.getenv("VLM_MODEL", "claude-sonnet-4-6")

DASHBOARD_HOST: str = os.getenv("DASHBOARD_HOST", "0.0.0.0")
DASHBOARD_PORT: int = int(os.getenv("DASHBOARD_PORT", "8000"))
