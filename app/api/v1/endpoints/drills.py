"""Coach drill library endpoints."""

from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.dependencies.auth import require_coach
from app.models.enums import DrillCategory, DrillDifficulty, DrillStatus
from app.repositories.drill_repository import DrillFilters
from app.schemas.auth import CurrentUser
from app.schemas.drill import DrillCreate, DrillListResponse, DrillResponse, DrillUpdate
from app.services.drill_service import DrillService

router = APIRouter(prefix="/drills", tags=["drills"])


def get_service(db: Session = Depends(get_db)) -> DrillService:
    return DrillService(db)


@router.post("", response_model=DrillResponse, status_code=status.HTTP_201_CREATED)
def create_drill(
    payload: DrillCreate,
    user: CurrentUser = Depends(require_coach),
    service: DrillService = Depends(get_service),
) -> DrillResponse:
    return service.create(payload, user)


@router.get("", response_model=DrillListResponse)
def list_drills(
    user: CurrentUser = Depends(require_coach),
    service: DrillService = Depends(get_service),
    search: str | None = None,
    category: DrillCategory | None = None,
    difficulty: DrillDifficulty | None = None,
    drill_status: DrillStatus | None = Query(default=None, alias="status"),
    tag: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(settings.default_page_size, ge=1, le=settings.max_page_size),
    sort_by: str = Query("updated_at", pattern="^(title|created_at|updated_at)$"),
    sort_order: str = Query("desc", pattern="^(asc|desc)$"),
) -> DrillListResponse:
    return service.list(
        DrillFilters(
            user.id,
            page,
            page_size,
            search,
            category,
            difficulty,
            drill_status,
            tag,
            sort_by,
            sort_order,
        )
    )


@router.get("/{drill_id}", response_model=DrillResponse)
def get_drill(
    drill_id: UUID,
    user: CurrentUser = Depends(require_coach),
    service: DrillService = Depends(get_service),
) -> DrillResponse:
    return service.get(drill_id, user.id)


@router.patch("/{drill_id}", response_model=DrillResponse)
def update_drill(
    drill_id: UUID,
    payload: DrillUpdate,
    user: CurrentUser = Depends(require_coach),
    service: DrillService = Depends(get_service),
) -> DrillResponse:
    return service.update(drill_id, payload, user.id)


@router.delete("/{drill_id}", status_code=status.HTTP_204_NO_CONTENT)
def archive_drill(
    drill_id: UUID,
    user: CurrentUser = Depends(require_coach),
    service: DrillService = Depends(get_service),
) -> Response:
    service.archive(drill_id, user.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{drill_id}/restore", response_model=DrillResponse)
def restore_drill(
    drill_id: UUID,
    user: CurrentUser = Depends(require_coach),
    service: DrillService = Depends(get_service),
) -> DrillResponse:
    return service.restore(drill_id, user.id)
