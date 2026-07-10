"""Athlete timeline API endpoints."""

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.dependencies.auth import require_coach
from app.repositories.athlete_repository import AthleteRepository
from app.repositories.timeline_repository import TimelineListFilters
from app.schemas.auth import CurrentUser
from app.schemas.timeline import TimelineListResponse
from app.services.timeline_service import TimelineService
from app.core.exceptions import NotFoundError

router = APIRouter(prefix="/athletes/{athlete_id}/timeline", tags=["timeline"])


def get_timeline_service(db: Session = Depends(get_db)) -> TimelineService:
    """Provide the timeline service."""
    return TimelineService(db)


@router.get("", response_model=TimelineListResponse)
def list_timeline(
    athlete_id: UUID,
    current_user: CurrentUser = Depends(require_coach),
    timeline_service: TimelineService = Depends(get_timeline_service),
    db: Session = Depends(get_db),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=settings.default_page_size, ge=1, le=settings.max_page_size),
    event_type: str | None = Query(default=None, max_length=100),
    start_date: datetime | None = Query(default=None),
    end_date: datetime | None = Query(default=None),
) -> TimelineListResponse:
    """List athlete timeline events newest first."""
    if AthleteRepository(db).get_accessible_for_coach(athlete_id, current_user.id) is None:
        raise NotFoundError("Athlete not found.")
    filters = TimelineListFilters(
        athlete_id=athlete_id,
        page=page,
        page_size=page_size,
        event_type=event_type,
        start_date=start_date,
        end_date=end_date,
    )
    return timeline_service.list_events(filters)
