"""Timeline domain service."""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.timeline import TimelineEvent
from app.repositories.timeline_repository import TimelineListFilters, TimelineRepository
from app.schemas.timeline import TimelineListResponse
from app.services.pagination import total_pages


class TimelineService:
    """Create and read athlete timeline events."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.timeline_repository = TimelineRepository(db)

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
    ) -> TimelineEvent:
        """Create a timeline event in the caller's active transaction."""
        event = TimelineEvent(
            athlete_id=athlete_id,
            event_type=event_type,
            title=title,
            description=description,
            source_service=source_service,
            source_entity_type=source_entity_type,
            source_entity_id=str(source_entity_id) if source_entity_id else None,
            metadata_json=metadata or {},
            occurred_at=occurred_at or datetime.now(UTC),
            created_by_user_id=created_by_user_id,
        )
        return self.timeline_repository.add(event)

    def create_internal_event(self, **kwargs: Any) -> TimelineEvent:
        """Internal extension point for future trusted service integrations."""
        return self.create_event(**kwargs)

    def list_events(self, filters: TimelineListFilters) -> TimelineListResponse:
        """Return paginated timeline events."""
        items, total = self.timeline_repository.list_for_athlete(filters)
        return TimelineListResponse(
            items=items,
            page=filters.page,
            page_size=filters.page_size,
            total=total,
            total_pages=total_pages(total, filters.page_size),
        )
