"""Pydantic schemas for the athlete service."""

from app.schemas.athlete import AthleteCreate, AthleteDetail, AthleteListResponse, AthleteSummary, AthleteUpdate
from app.schemas.auth import CurrentUser
from app.schemas.common import ErrorResponse
from app.schemas.goal import GoalCreate, GoalListResponse, GoalResponse, GoalUpdate
from app.schemas.timeline import TimelineEventResponse, TimelineListResponse

__all__ = [
    "AthleteCreate",
    "AthleteDetail",
    "AthleteListResponse",
    "AthleteSummary",
    "AthleteUpdate",
    "CurrentUser",
    "ErrorResponse",
    "GoalCreate",
    "GoalListResponse",
    "GoalResponse",
    "GoalUpdate",
    "TimelineEventResponse",
    "TimelineListResponse",
]
