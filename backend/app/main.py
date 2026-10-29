"""Main entry point for the KnowledgeSmith AI backend application."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from backend.app.api.routes import router as api_router
from backend.app.config import settings
from backend.app.core.logging_config import setup_logging

logger = setup_logging(settings.log_level)

app = FastAPI(
    title="KnowledgeSmith AI",
    description="An Autonomous Knowledge Engineering Platform for Open Knowledge Format (OKF) artifacts",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(api_router)

# Static directory setup
STATIC_DIR = Path(__file__).parent / "static"
STATIC_DIR.mkdir(parents=True, exist_ok=True)

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/", response_class=HTMLResponse)
def index_page() -> Any:
    """Serve the KnowledgeSmith AI web dashboard."""
    index_file = STATIC_DIR / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return HTMLResponse(
        """
        <!DOCTYPE html>
        <html>
        <head><title>KnowledgeSmith AI</title></head>
        <body style="font-family:sans-serif;padding:2rem;background:#0d1117;color:#c9d1d9;">
            <h1>KnowledgeSmith AI</h1>
            <p>An Autonomous Knowledge Engineering Platform</p>
            <p><a href="/docs" style="color:#58a6ff;">API Documentation (Swagger UI)</a></p>
        </body>
        </html>
        """
    )


@app.get("/health")
def health_check():
    """Top-level health check."""
    return {"status": "ok", "app": "KnowledgeSmith AI", "version": "0.1.0"}
