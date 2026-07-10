"""API v1 router."""

from fastapi import APIRouter

from app.api.v1.endpoints.athletes import router as athletes_router
from app.api.v1.endpoints.goals import router as goals_router
from app.api.v1.endpoints.timeline import router as timeline_router

api_router = APIRouter()
api_router.include_router(athletes_router)
api_router.include_router(goals_router)
api_router.include_router(timeline_router)
