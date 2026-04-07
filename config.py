from __future__ import annotations
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
IMAGES_DIR = DATA_DIR / "images"
REPORTS_DIR = DATA_DIR / "reports"
BASELINES_DIR = DATA_DIR / "baselines"
DB_PATH = DATA_DIR / "oversight.db"

# "local" uses Ollama (free, runs on GPU)
# "anthropic" uses Claude API (swap in before MVP)
VLM_BACKEND: str = os.getenv("VLM_BACKEND", "local")

ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
VLM_MODEL: str = os.getenv("VLM_MODEL", "claude-sonnet-4-6")

LOCAL_MODEL: str = os.getenv("LOCAL_MODEL", "qwen2.5vl:7b")
OLLAMA_URL: str = os.getenv("OLLAMA_URL", "http://localhost:11434")

DASHBOARD_HOST: str = os.getenv("DASHBOARD_HOST", "0.0.0.0")
DASHBOARD_PORT: int = int(os.getenv("DASHBOARD_PORT", "8000"))

PDF_RETENTION_HOURS: int = int(os.getenv("PDF_RETENTION_HOURS", "72"))

# ── Mock auth (Phase 1) ────────────────────────────────────────────────────────
# Hardcoded credentials for demo. Replace with real auth before production.
DEMO_USERNAME: str = os.getenv("DEMO_USERNAME", "admin")
DEMO_PASSWORD: str = os.getenv("DEMO_PASSWORD", "oversight")

# ── Credential encryption (Phase 1) ───────────────────────────────────────────
# Fernet symmetric key for encrypting camera_url at rest.
# If not set, a key is generated and stored to data/secret.key.
def _load_or_create_key() -> bytes:
    key_path = DATA_DIR / "secret.key"
    env_key = os.getenv("OVERSIGHT_SECRET_KEY", "")
    if env_key:
        return env_key.encode()
    if key_path.exists():
        return key_path.read_bytes().strip()
    from cryptography.fernet import Fernet
    key = Fernet.generate_key()
    key_path.parent.mkdir(parents=True, exist_ok=True)
    key_path.write_bytes(key)
    return key

try:
    from cryptography.fernet import Fernet as _Fernet
    FERNET_KEY: bytes = _load_or_create_key()
    _fernet = _Fernet(FERNET_KEY)
    def encrypt_str(s: str) -> str:
        return _fernet.encrypt(s.encode()).decode()
    def decrypt_str(s: str) -> str:
        return _fernet.decrypt(s.encode()).decode()
except ImportError:
    # cryptography not installed — passthrough (no encryption)
    def encrypt_str(s: str) -> str:  # type: ignore[misc]
        return s
    def decrypt_str(s: str) -> str:  # type: ignore[misc]
        return s
