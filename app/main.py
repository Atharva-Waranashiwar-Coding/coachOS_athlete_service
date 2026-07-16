"""FastAPI application entry point for the Athlete Service."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.internal.athlete_user_links import router as internal_athlete_links_router
from app.api.internal.timeline import router as internal_timeline_router
from app.api.v1.router import api_router
from app.core.config import settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import configure_logging
from app.db.session import SessionLocal

configure_logging()

app = FastAPI(
    title="CoachOS Athlete Service",
    description="Athlete profile, relationship, goal, and timeline service for CoachOS.",
    version="0.1.0",
)
register_exception_handlers(app)

if settings.cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

app.include_router(api_router, prefix=settings.api_v1_prefix)
app.include_router(internal_timeline_router, prefix=settings.internal_api_prefix)
app.include_router(internal_athlete_links_router, prefix=settings.internal_api_prefix)


@app.get("/health/live", tags=["health"])
def live_check() -> dict[str, str]:
    """Return liveness status."""
    return {"status": "ok", "service": "athlete", "environment": settings.app_env}


@app.get("/health/ready", tags=["health"])
def ready_check() -> dict[str, str]:
    """Return readiness status after verifying database connectivity."""
    db: Session = SessionLocal()
    try:
        db.execute(text("SELECT 1"))
    finally:
        db.close()
    return {"status": "ready", "service": "athlete"}


@app.get("/health", tags=["health"])
def health_check() -> dict[str, str]:
    """Backward-compatible health endpoint."""
    return live_check()
