"""Entrypoint — starts the dashboard server.

Camera zone loops are started individually via the dashboard
once a zone is configured.
"""
import logging
import uvicorn
import config

logging.basicConfig(level=logging.INFO)

if __name__ == "__main__":
    uvicorn.run(
        "dashboard.main:app",
        host=config.DASHBOARD_HOST,
        port=config.DASHBOARD_PORT,
        reload=False,
    )
