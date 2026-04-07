"""Entrypoint — starts the dashboard server.

Camera zone loops are started individually via the dashboard
once a zone is configured.
"""
import logging
import uvicorn
import config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)

# Quiet down noisy third-party loggers
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("anthropic").setLevel(logging.WARNING)
logging.getLogger("apscheduler").setLevel(logging.WARNING)
logging.getLogger("multipart").setLevel(logging.WARNING)

if __name__ == "__main__":
    uvicorn.run(
        "dashboard.main:app",
        host=config.DASHBOARD_HOST,
        port=config.DASHBOARD_PORT,
        reload=False,
        log_config=None,   # don't let uvicorn wipe our logging setup
        log_level="info",  # uvicorn still respects this for its own loggers
    )
