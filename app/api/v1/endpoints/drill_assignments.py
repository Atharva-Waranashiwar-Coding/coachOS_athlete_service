"""Athlete drill assignment endpoints."""

from datetime import date
from uuid import UUID

from fastapi import APIRouter, Body, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.dependencies.athlete_access import get_accessible_athlete, require_primary_coach_access
from app.dependencies.auth import get_bearer_token, require_coach
from app.models.athlete import Athlete
from app.models.enums import DrillAssignmentStatus, DrillCategory
from app.repositories.drill_assignment_repository import AssignmentFilters
from app.schemas.auth import CurrentUser
from app.schemas.drill_assignment import (
    AssignmentCancelRequest,
    AssignmentCompleteRequest,
    DrillAssignmentCreate,
    DrillAssignmentListResponse,
    DrillAssignmentResponse,
    DrillAssignmentUpdate,
)
from app.services.drill_assignment_service import DrillAssignmentService

router = APIRouter(prefix="/athletes/{athlete_id}/drill-assignments", tags=["drill-assignments"])


def get_service(db: Session = Depends(get_db)) -> DrillAssignmentService:
    return DrillAssignmentService(db)


@router.post("", response_model=DrillAssignmentResponse, status_code=status.HTTP_201_CREATED)
def create_assignment(
    payload: DrillAssignmentCreate = Body(..., discriminator="mode"),
    athlete: Athlete = Depends(require_primary_coach_access),
    user: CurrentUser = Depends(require_coach),
    bearer_token: str = Depends(get_bearer_token),
    service: DrillAssignmentService = Depends(get_service),
) -> DrillAssignmentResponse:
    return service.create(athlete, payload, user, bearer_token)


@router.get("", response_model=DrillAssignmentListResponse)
def list_assignments(
    athlete_id: UUID,
    _: Athlete = Depends(get_accessible_athlete),
    user: CurrentUser = Depends(require_coach),
    service: DrillAssignmentService = Depends(get_service),
    assignment_status: DrillAssignmentStatus | None = Query(default=None, alias="status"),
    category: DrillCategory | None = None,
    priority: int | None = Query(default=None, ge=1, le=5),
    due_before: date | None = None,
    due_after: date | None = None,
    source_review_id: UUID | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(settings.default_drill_assignment_page_size, ge=1, le=settings.max_page_size),
    sort_by: str = Query("assigned_at", pattern="^(assigned_at|due_date|priority|updated_at)$"),
    sort_order: str = Query("desc", pattern="^(asc|desc)$"),
) -> DrillAssignmentListResponse:
    return service.list(
        AssignmentFilters(
            athlete_id,
            page,
            page_size,
            assignment_status,
            category,
            priority,
            due_before,
            due_after,
            source_review_id,
            sort_by,
            sort_order,
        )
    )


@router.get("/{assignment_id}", response_model=DrillAssignmentResponse)
def get_assignment(
    athlete_id: UUID,
    assignment_id: UUID,
    _: Athlete = Depends(get_accessible_athlete),
    service: DrillAssignmentService = Depends(get_service),
) -> DrillAssignmentResponse:
    return service.get(athlete_id, assignment_id)


@router.patch("/{assignment_id}", response_model=DrillAssignmentResponse)
def update_assignment(
    athlete_id: UUID,
    assignment_id: UUID,
    payload: DrillAssignmentUpdate,
    _: Athlete = Depends(require_primary_coach_access),
    user: CurrentUser = Depends(require_coach),
    service: DrillAssignmentService = Depends(get_service),
) -> DrillAssignmentResponse:
    return service.update(athlete_id, assignment_id, payload, user)


@router.post("/{assignment_id}/start", response_model=DrillAssignmentResponse)
def start_assignment(
    athlete_id: UUID,
    assignment_id: UUID,
    _: Athlete = Depends(require_primary_coach_access),
    user: CurrentUser = Depends(require_coach),
    service: DrillAssignmentService = Depends(get_service),
) -> DrillAssignmentResponse:
    return service.start(athlete_id, assignment_id, user)


@router.post("/{assignment_id}/complete", response_model=DrillAssignmentResponse)
def complete_assignment(
    athlete_id: UUID,
    assignment_id: UUID,
    payload: AssignmentCompleteRequest,
    _: Athlete = Depends(require_primary_coach_access),
    user: CurrentUser = Depends(require_coach),
    service: DrillAssignmentService = Depends(get_service),
) -> DrillAssignmentResponse:
    return service.complete(athlete_id, assignment_id, payload, user)


@router.post("/{assignment_id}/cancel", response_model=DrillAssignmentResponse)
def cancel_assignment(
    athlete_id: UUID,
    assignment_id: UUID,
    payload: AssignmentCancelRequest,
    _: Athlete = Depends(require_primary_coach_access),
    user: CurrentUser = Depends(require_coach),
    service: DrillAssignmentService = Depends(get_service),
) -> DrillAssignmentResponse:
    return service.cancel(athlete_id, assignment_id, payload, user)
