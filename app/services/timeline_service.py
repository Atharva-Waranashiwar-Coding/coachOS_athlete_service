from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, NotFoundError
from app.models.enums import EventCategory, TimelineVisibility
from app.models.timeline import TimelineEvent
from app.repositories.athlete_repository import AthleteRepository
from app.repositories.timeline_repository import TimelineListFilters, TimelineRepository
from app.schemas.timeline import TimelineEventResponse, TimelineIngestionRequest, TimelineListResponse
from app.services.pagination import total_pages


def category_for(event_type: str) -> EventCategory:
    if event_type.startswith("goal_"):
        return EventCategory.GOAL
    if event_type.startswith(("athlete_", "injury_note_")):
        return EventCategory.PROFILE
    return EventCategory.SYSTEM


class TimelineService:
    def __init__(self, db: Session) -> None:
        self.db, self.timeline_repository = db, TimelineRepository(db)

    def create_event(
        self,
        *,
        athlete_id: UUID,
        event_type: str,
        title: str,
        source_service: str = "athlete-service",
        description: str | None = None,
        source_entity_type: str | None = None,
        source_entity_id: UUID | str | None = None,
        metadata: dict[str, Any] | None = None,
        created_by_user_id: UUID | None = None,
        occurred_at: datetime | None = None,
        event_category: EventCategory | None = None,
        visibility: TimelineVisibility | None = None,
    ) -> TimelineEvent:
        safe_metadata = metadata or {}
        if event_type == "injury_note_updated":
            safe_metadata = {"changed": True}
        event = TimelineEvent(
            athlete_id=athlete_id,
            event_type=event_type,
            event_category=event_category or category_for(event_type),
            title=title.strip(),
            description=description,
            source_service=source_service,
            source_entity_type=source_entity_type,
            source_entity_id=str(source_entity_id) if source_entity_id else None,
            metadata_json=safe_metadata,
            occurred_at=occurred_at or datetime.now(UTC),
            actor_user_id=created_by_user_id,
            schema_version=1,
            visibility=visibility
            or (
                TimelineVisibility.COACH_ONLY
                if event_type == "injury_note_updated"
                else TimelineVisibility.ATHLETE_VISIBLE
            ),
        )
        return self.timeline_repository.add(event)

    def ingest(self, payload: TimelineIngestionRequest) -> tuple[TimelineEventResponse, bool]:
        if AthleteRepository(self.db).get_by_id(payload.athlete_id) is None:
            raise NotFoundError("Athlete not found.")
        existing = self.timeline_repository.by_external_id(payload.event_id)
        if existing:
            comparable = {
                "athlete_id": existing.athlete_id,
                "event_type": existing.event_type,
                "event_category": existing.event_category,
                "title": existing.title,
                "description": existing.description,
                "source_service": existing.source_service,
                "source_entity_type": existing.source_entity_type,
                "source_entity_id": existing.source_entity_id,
                "actor_user_id": existing.actor_user_id,
                "occurred_at": existing.occurred_at,
                "metadata": existing.metadata_json,
                "schema_version": existing.schema_version,
                "visibility": existing.visibility,
            }
            requested = payload.model_dump(exclude={"event_id"})
            if comparable != requested:
                raise ConflictError("Event id was already used with different content.")
            return TimelineEventResponse.model_validate(existing), False
        event = TimelineEvent(
            external_event_id=payload.event_id,
            metadata_json=payload.metadata,
            **payload.model_dump(exclude={"event_id", "metadata"}),
        )
        self.timeline_repository.add(event)
        try:
            self.db.commit()
            self.db.refresh(event)
        except Exception:
            self.db.rollback()
            raise
        return TimelineEventResponse.model_validate(event), True

    def list_events(self, filters: TimelineListFilters) -> TimelineListResponse:
        items, total = self.timeline_repository.list_for_athlete(filters)
        return TimelineListResponse(
            items=items,
            page=filters.page,
            page_size=filters.page_size,
            total=total,
            total_pages=total_pages(total, filters.page_size),
        )
