"""API v1 router."""

from fastapi import APIRouter

from app.api.v1.endpoints.athlete_invitations import router as athlete_invitations_router
from app.api.v1.endpoints.athlete_self import router as athlete_self_router
from app.api.v1.endpoints.athletes import router as athletes_router
from app.api.v1.endpoints.drill_assignments import router as drill_assignments_router
from app.api.v1.endpoints.drills import router as drills_router
from app.api.v1.endpoints.goals import router as goals_router
from app.api.v1.endpoints.timeline import router as timeline_router

api_router = APIRouter()
api_router.include_router(athletes_router)
api_router.include_router(athlete_invitations_router)
api_router.include_router(athlete_self_router)
api_router.include_router(drills_router)
api_router.include_router(drill_assignments_router)
api_router.include_router(goals_router)
api_router.include_router(timeline_router)
