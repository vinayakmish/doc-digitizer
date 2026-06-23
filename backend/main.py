"""
DocDigitizer API — FastAPI Application Entry Point.

Configures the FastAPI application with CORS middleware, static file
serving, health-check endpoints, and router registration. Creates
required upload/output directories on startup.

Run with:
    uvicorn main:app --reload
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from config import settings
from utils.helpers import ensure_directory, get_timestamp

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
BACKEND_DIR = Path(__file__).resolve().parent
FRONTEND_DIR = (BACKEND_DIR / ".." / "frontend").resolve()


# ---------------------------------------------------------------------------
# Lifespan (replaces deprecated startup/shutdown events)
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application lifespan handler — runs setup on startup and teardown on shutdown."""
    # --- Startup ---
    logger.info("Starting DocDigitizer API …")

    # Ensure upload and output directories exist
    ensure_directory(settings.upload_dir_path)
    logger.info("Upload directory: %s", settings.upload_dir_path)

    ensure_directory(settings.output_dir_path)
    logger.info("Output directory: %s", settings.output_dir_path)

    if settings.GEMINI_API_KEY:
        logger.info("Gemini API key is configured (model: %s).", settings.GEMINI_MODEL)
    else:
        logger.warning(
            "GEMINI_API_KEY is not set — AI analysis features will be unavailable."
        )

    logger.info("DocDigitizer API is ready.")
    yield
    # --- Shutdown ---
    logger.info("Shutting down DocDigitizer API …")


# ---------------------------------------------------------------------------
# FastAPI Application
# ---------------------------------------------------------------------------
app = FastAPI(
    title="DocDigitizer API",
    description=(
        "AI-powered Document Digitization System. Upload documents in various "
        "formats and receive structured data extraction powered by Google Gemini, "
        "Tesseract OCR, and intelligent post-processing."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# ---------------------------------------------------------------------------
# CORS Middleware (permissive for development)
# ---------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Static Files — serve the frontend
# ---------------------------------------------------------------------------
if FRONTEND_DIR.is_dir():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")
    # Mount subdirectories at their natural paths so relative URLs in
    # index.html (e.g. css/styles.css, js/app.js) resolve correctly.
    css_dir = FRONTEND_DIR / "css"
    js_dir = FRONTEND_DIR / "js"
    if css_dir.is_dir():
        app.mount("/css", StaticFiles(directory=str(css_dir)), name="css")
    if js_dir.is_dir():
        app.mount("/js", StaticFiles(directory=str(js_dir)), name="js")
    logger.info("Mounted frontend static files from: %s", FRONTEND_DIR)
else:
    logger.warning(
        "Frontend directory not found at %s — static file serving disabled.",
        FRONTEND_DIR,
    )

# ---------------------------------------------------------------------------
# Router Registration
# ---------------------------------------------------------------------------
# Import is deferred to allow the router module to be optional during early
# development when services haven't been implemented yet.
try:
    from routers.documents import router as documents_router

    app.include_router(documents_router, prefix="/api")
    logger.info("Registered /api router from routers.documents.")
except ImportError:
    logger.warning(
        "routers.documents not found or not importable — /api routes unavailable."
    )


# ---------------------------------------------------------------------------
# Health Check
# ---------------------------------------------------------------------------
@app.get(
    "/api/health",
    tags=["system"],
    summary="Health check",
    response_model=dict,
)
async def health_check() -> dict:
    """Return service health status and metadata.

    Returns:
        A JSON object with status, timestamp, version, and configuration flags.
    """
    return {
        "status": "healthy",
        "timestamp": get_timestamp(),
        "version": app.version,
        "gemini_configured": settings.GEMINI_API_KEY is not None,
        "upload_dir": str(settings.upload_dir_path),
        "output_dir": str(settings.output_dir_path),
    }


# ---------------------------------------------------------------------------
# Root — Serve Frontend
# ---------------------------------------------------------------------------
@app.get("/", include_in_schema=False, response_model=None)
async def root():
    """Serve the frontend index.html at the root path.

    Falls back to a JSON message if the frontend has not been built yet.
    """
    index_path = FRONTEND_DIR / "index.html"
    if index_path.is_file():
        return FileResponse(str(index_path), media_type="text/html")

    return JSONResponse(
        content={
            "message": "DocDigitizer API is running. Frontend not found.",
            "docs": "/docs",
            "health": "/api/health",
        }
    )
