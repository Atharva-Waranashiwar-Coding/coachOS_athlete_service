"""Athlete goal API endpoints."""

from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.dependencies.auth import require_coach
from app.models.enums import GoalCategory, GoalStatus
from app.repositories.goal_repository import GoalListFilters
from app.schemas.auth import CurrentUser
from app.schemas.goal import GoalCreate, GoalListResponse, GoalResponse, GoalUpdate
from app.services.goal_service import GoalService

router = APIRouter(prefix="/athletes/{athlete_id}/goals", tags=["goals"])


def get_goal_service(db: Session = Depends(get_db)) -> GoalService:
    """Provide the goal service."""
    return GoalService(db)


@router.post("", response_model=GoalResponse, status_code=status.HTTP_201_CREATED)
def create_goal(
    athlete_id: UUID,
    payload: GoalCreate,
    current_user: CurrentUser = Depends(require_coach),
    goal_service: GoalService = Depends(get_goal_service),
) -> GoalResponse:
    """Create a goal for an accessible athlete."""
    return goal_service.create_goal(athlete_id, payload, current_user)


@router.get("", response_model=GoalListResponse)
def list_goals(
    athlete_id: UUID,
    current_user: CurrentUser = Depends(require_coach),
    goal_service: GoalService = Depends(get_goal_service),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=settings.default_page_size, ge=1, le=settings.max_page_size),
    status_filter: GoalStatus | None = Query(default=None, alias="status"),
    category: GoalCategory | None = Query(default=None),
) -> GoalListResponse:
    """List goals for an accessible athlete."""
    filters = GoalListFilters(
        athlete_id=athlete_id,
        page=page,
        page_size=page_size,
        status=status_filter,
        category=category,
    )
    return goal_service.list_goals(filters, current_user)


@router.get("/{goal_id}", response_model=GoalResponse)
def get_goal(
    athlete_id: UUID,
    goal_id: UUID,
    current_user: CurrentUser = Depends(require_coach),
    goal_service: GoalService = Depends(get_goal_service),
) -> GoalResponse:
    """Return one goal for an accessible athlete."""
    return goal_service.get_goal(athlete_id, goal_id, current_user)


@router.patch("/{goal_id}", response_model=GoalResponse)
def update_goal(
    athlete_id: UUID,
    goal_id: UUID,
    payload: GoalUpdate,
    current_user: CurrentUser = Depends(require_coach),
    goal_service: GoalService = Depends(get_goal_service),
) -> GoalResponse:
    """Update a goal as the primary coach."""
    return goal_service.update_goal(athlete_id, goal_id, payload, current_user)


@router.delete("/{goal_id}", status_code=status.HTTP_204_NO_CONTENT)
def cancel_goal(
    athlete_id: UUID,
    goal_id: UUID,
    current_user: CurrentUser = Depends(require_coach),
    goal_service: GoalService = Depends(get_goal_service),
) -> Response:
    """Cancel a goal without deleting timeline history."""
    goal_service.cancel_goal(athlete_id, goal_id, current_user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
