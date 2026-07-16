"""Coach-owned drill library use cases."""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.exceptions import BadRequestError, NotFoundError
from app.models.drill import Drill
from app.models.enums import DrillStatus, DrillVisibility
from app.repositories.drill_repository import DrillFilters, DrillRepository
from app.schemas.auth import CurrentUser
from app.schemas.drill import DrillCreate, DrillListResponse, DrillResponse, DrillUpdate
from app.services.pagination import total_pages


class DrillService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repository = DrillRepository(db)

    def create(self, payload: DrillCreate, user: CurrentUser) -> DrillResponse:
        drill = Drill(
            created_by_user_id=user.id,
            visibility=DrillVisibility.PRIVATE,
            video_url=str(payload.video_url) if payload.video_url else None,
            **payload.model_dump(exclude={"video_url"}),
        )
        self.repository.add(drill)
        self.db.commit()
        self.db.refresh(drill)
        return DrillResponse.model_validate(drill)

    def list(self, filters: DrillFilters) -> DrillListResponse:
        items, total = self.repository.list(filters)
        return DrillListResponse(
            items=[DrillResponse.model_validate(item) for item in items],
            page=filters.page,
            page_size=filters.page_size,
            total=total,
            total_pages=total_pages(total, filters.page_size),
        )

    def get_model(self, drill_id: UUID, user_id: UUID) -> Drill:
        drill = self.repository.get_accessible(drill_id, user_id)
        if not drill:
            raise NotFoundError("Drill not found.")
        return drill

    def get(self, drill_id: UUID, user_id: UUID) -> DrillResponse:
        return DrillResponse.model_validate(self.get_model(drill_id, user_id))

    def update(self, drill_id: UUID, payload: DrillUpdate, user_id: UUID) -> DrillResponse:
        drill = self.get_model(drill_id, user_id)
        self._require_owner(drill, user_id)
        data = payload.model_dump(exclude_unset=True)
        if "video_url" in data and data["video_url"] is not None:
            data["video_url"] = str(data["video_url"])
        for field, value in data.items():
            setattr(drill, field, value)
        self.db.commit()
        self.db.refresh(drill)
        return DrillResponse.model_validate(drill)

    def archive(self, drill_id: UUID, user_id: UUID) -> None:
        drill = self.get_model(drill_id, user_id)
        self._require_owner(drill, user_id)
        drill.status, drill.archived_at = DrillStatus.ARCHIVED, datetime.now(UTC)
        self.db.commit()

    def restore(self, drill_id: UUID, user_id: UUID) -> DrillResponse:
        drill = self.get_model(drill_id, user_id)
        self._require_owner(drill, user_id)
        drill.status, drill.archived_at = DrillStatus.ACTIVE, None
        self.db.commit()
        self.db.refresh(drill)
        return DrillResponse.model_validate(drill)

    @staticmethod
    def _require_owner(drill: Drill, user_id: UUID) -> None:
        if drill.visibility == DrillVisibility.SYSTEM or drill.created_by_user_id != user_id:
            raise NotFoundError("Drill not found.")
        if drill.status not in {DrillStatus.ACTIVE, DrillStatus.ARCHIVED}:
            raise BadRequestError("Drill cannot be modified.")
