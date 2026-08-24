"""FastAPI application entry point for CodeX."""

import os
from pathlib import Path
import sys

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Support the beginner-friendly `uvicorn main:app` command when the working
# directory is backend/, while retaining normal `backend.main` package imports.
if not __package__:
    project_root = str(Path(__file__).resolve().parent.parent)
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

from backend.routes.code_runner import router as code_runner_router
from backend.routes.health import router as health_router

DEFAULT_CORS_ORIGINS = (
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:4173",
    "http://127.0.0.1:4173",
)


def allowed_cors_origins() -> list[str]:
    """Return configured frontend origins or the safe local-development defaults."""

    configured = os.environ.get("CODEX_CORS_ORIGINS", "")
    if not configured.strip():
        return list(DEFAULT_CORS_ORIGINS)

    origins = [origin.strip().rstrip("/") for origin in configured.split(",")]
    return [origin for origin in origins if origin]


def create_app() -> FastAPI:
    """Create and configure the CodeX API application."""

    application = FastAPI(
        title="CodeX API",
        description="Development API for the CodeX online code editor.",
        version="1.0.0",
    )

    application.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_cors_origins(),
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type"],
    )

    application.include_router(health_router, prefix="/api")
    application.include_router(code_runner_router, prefix="/api")
    return application


app = create_app()
