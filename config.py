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

# "local" uses Ollama (free, runs on GPU)
# "anthropic" uses Claude API (swap in before MVP)
VLM_BACKEND: str = os.getenv("VLM_BACKEND", "local")

ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
VLM_MODEL: str = os.getenv("VLM_MODEL", "claude-sonnet-4-6")

LOCAL_MODEL: str = os.getenv("LOCAL_MODEL", "qwen2-vl:7b")
OLLAMA_URL: str = os.getenv("OLLAMA_URL", "http://localhost:11434")

DASHBOARD_HOST: str = os.getenv("DASHBOARD_HOST", "0.0.0.0")
DASHBOARD_PORT: int = int(os.getenv("DASHBOARD_PORT", "8000"))
