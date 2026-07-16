"""Athlete self-service endpoints resolved exclusively from the JWT identity link."""

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.dependencies.auth import get_bearer_token
from app.dependencies.current_athlete import get_current_athlete
from app.models.enums import DrillAssignmentStatus, EventCategory, GoalCategory, GoalStatus
from app.schemas.athlete_self import (
    AthleteCompleteRequest,
    AthleteDashboardResponse,
    AthleteDrillAssignmentDetail,
    AthleteDrillAssignmentListResponse,
    AthleteGoalListResponse,
    AthleteProgressRequest,
    AthleteSelfProfileResponse,
    AthleteTimelineListResponse,
)
from app.schemas.auth import CurrentAthlete
from app.services.athlete_self_service import AthleteSelfService

router = APIRouter(prefix="/athlete", tags=["athlete-self"])


@router.get("/me", response_model=AthleteSelfProfileResponse)
def get_profile(
    current: CurrentAthlete = Depends(get_current_athlete),
    db: Session = Depends(get_db),
) -> AthleteSelfProfileResponse:
    return AthleteSelfService(db).profile(current)


@router.get("/dashboard", response_model=AthleteDashboardResponse)
def get_dashboard(
    current: CurrentAthlete = Depends(get_current_athlete),
    bearer_token: str = Depends(get_bearer_token),
    db: Session = Depends(get_db),
) -> AthleteDashboardResponse:
    return AthleteSelfService(db).dashboard(current, bearer_token)


@router.get("/timeline", response_model=AthleteTimelineListResponse)
def list_timeline(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=settings.default_page_size, ge=1, le=settings.max_page_size),
    event_type: str | None = Query(default=None, min_length=1, max_length=100),
    event_category: EventCategory | None = None,
    source_service: str | None = Query(default=None, min_length=1, max_length=100),
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    current: CurrentAthlete = Depends(get_current_athlete),
    db: Session = Depends(get_db),
) -> AthleteTimelineListResponse:
    return AthleteSelfService(db).timeline_list(
        current,
        page=page,
        page_size=page_size,
        event_type=event_type,
        event_category=event_category,
        source_service=source_service,
        start_date=start_date,
        end_date=end_date,
    )


@router.get("/goals", response_model=AthleteGoalListResponse)
def list_goals(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=settings.default_page_size, ge=1, le=settings.max_page_size),
    status: GoalStatus | None = None,
    category: GoalCategory | None = None,
    current: CurrentAthlete = Depends(get_current_athlete),
    db: Session = Depends(get_db),
) -> AthleteGoalListResponse:
    return AthleteSelfService(db).goals_list(
        current,
        page=page,
        page_size=page_size,
        status=status,
        category=category,
    )


@router.get("/drill-assignments", response_model=AthleteDrillAssignmentListResponse)
def list_assignments(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=settings.default_drill_assignment_page_size, ge=1, le=settings.max_page_size),
    status: DrillAssignmentStatus | None = None,
    due_before: date | None = None,
    due_after: date | None = None,
    priority: int | None = Query(default=None, ge=1, le=5),
    sort_by: Literal["assigned_at", "due_date", "priority", "completion_percentage"] | None = None,
    sort_order: Literal["asc", "desc"] = "desc",
    current: CurrentAthlete = Depends(get_current_athlete),
    db: Session = Depends(get_db),
) -> AthleteDrillAssignmentListResponse:
    return AthleteSelfService(db).assignments_list(
        current,
        page=page,
        page_size=page_size,
        status=status,
        due_before=due_before,
        due_after=due_after,
        priority=priority,
        sort_by=sort_by,
        sort_order=sort_order,
    )


@router.get("/drill-assignments/{assignment_id}", response_model=AthleteDrillAssignmentDetail)
def get_assignment(
    assignment_id: UUID,
    current: CurrentAthlete = Depends(get_current_athlete),
    db: Session = Depends(get_db),
) -> AthleteDrillAssignmentDetail:
    return AthleteSelfService(db).assignment_detail(current, assignment_id)


@router.post("/drill-assignments/{assignment_id}/start", response_model=AthleteDrillAssignmentDetail)
def start_assignment(
    assignment_id: UUID,
    current: CurrentAthlete = Depends(get_current_athlete),
    db: Session = Depends(get_db),
) -> AthleteDrillAssignmentDetail:
    return AthleteSelfService(db).start_assignment(current, assignment_id)


@router.post("/drill-assignments/{assignment_id}/progress", response_model=AthleteDrillAssignmentDetail)
def update_assignment_progress(
    assignment_id: UUID,
    payload: AthleteProgressRequest,
    current: CurrentAthlete = Depends(get_current_athlete),
    db: Session = Depends(get_db),
) -> AthleteDrillAssignmentDetail:
    return AthleteSelfService(db).update_progress(current, assignment_id, payload)


@router.post("/drill-assignments/{assignment_id}/complete", response_model=AthleteDrillAssignmentDetail)
def complete_assignment(
    assignment_id: UUID,
    payload: AthleteCompleteRequest,
    current: CurrentAthlete = Depends(get_current_athlete),
    db: Session = Depends(get_db),
) -> AthleteDrillAssignmentDetail:
    return AthleteSelfService(db).complete_assignment(current, assignment_id, payload)
