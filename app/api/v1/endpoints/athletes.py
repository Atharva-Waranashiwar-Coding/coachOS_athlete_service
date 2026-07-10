"""Athlete API endpoints."""

from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.dependencies.auth import require_coach
from app.models.enums import AthleteStatus, Position
from app.repositories.athlete_repository import AthleteListFilters
from app.schemas.athlete import AthleteCreate, AthleteDetail, AthleteListResponse, AthleteUpdate
from app.schemas.auth import CurrentUser
from app.services.athlete_service import AthleteService

router = APIRouter(prefix="/athletes", tags=["athletes"])


def get_athlete_service(db: Session = Depends(get_db)) -> AthleteService:
    """Provide the athlete service."""
    return AthleteService(db)


@router.post("", response_model=AthleteDetail, status_code=status.HTTP_201_CREATED)
def create_athlete(
    payload: AthleteCreate,
    current_user: CurrentUser = Depends(require_coach),
    athlete_service: AthleteService = Depends(get_athlete_service),
) -> AthleteDetail:
    """Create an athlete and assign the current coach as primary coach."""
    return athlete_service.create_athlete(payload, current_user)


@router.get("", response_model=AthleteListResponse)
def list_athletes(
    current_user: CurrentUser = Depends(require_coach),
    athlete_service: AthleteService = Depends(get_athlete_service),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=settings.default_page_size, ge=1, le=settings.max_page_size),
    search: str | None = Query(default=None, max_length=100),
    status_filter: AthleteStatus | None = Query(default=None, alias="status"),
    primary_position: Position | None = Query(default=None),
    sort_by: str = Query(default="last_name", pattern="^(first_name|last_name|created_at|updated_at)$"),
    sort_order: str = Query(default="asc", pattern="^(asc|desc)$"),
) -> AthleteListResponse:
    """List athletes connected to the current coach."""
    filters = AthleteListFilters(
        coach_user_id=current_user.id,
        page=page,
        page_size=page_size,
        search=search,
        status=status_filter,
        primary_position=primary_position,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    return athlete_service.list_athletes(filters)


@router.get("/{athlete_id}", response_model=AthleteDetail)
def get_athlete(
    athlete_id: UUID,
    current_user: CurrentUser = Depends(require_coach),
    athlete_service: AthleteService = Depends(get_athlete_service),
) -> AthleteDetail:
    """Return an athlete profile visible to the current coach."""
    return athlete_service.get_athlete(athlete_id, current_user.id)


@router.patch("/{athlete_id}", response_model=AthleteDetail)
def update_athlete(
    athlete_id: UUID,
    payload: AthleteUpdate,
    current_user: CurrentUser = Depends(require_coach),
    athlete_service: AthleteService = Depends(get_athlete_service),
) -> AthleteDetail:
    """Update an athlete profile as the primary coach."""
    return athlete_service.update_athlete(athlete_id, payload, current_user)


@router.delete("/{athlete_id}", status_code=status.HTTP_204_NO_CONTENT)
def archive_athlete(
    athlete_id: UUID,
    current_user: CurrentUser = Depends(require_coach),
    athlete_service: AthleteService = Depends(get_athlete_service),
) -> Response:
    """Archive an athlete instead of hard deleting the row."""
    athlete_service.archive_athlete(athlete_id, current_user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{athlete_id}/restore", response_model=AthleteDetail)
def restore_athlete(
    athlete_id: UUID,
    current_user: CurrentUser = Depends(require_coach),
    athlete_service: AthleteService = Depends(get_athlete_service),
) -> AthleteDetail:
    """Restore an archived athlete."""
    return athlete_service.restore_athlete(athlete_id, current_user)
