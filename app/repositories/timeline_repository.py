from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.models.enums import EventCategory, TimelineVisibility
from app.models.timeline import TimelineEvent


@dataclass(frozen=True)
class TimelineListFilters:
    athlete_id: UUID
    page: int
    page_size: int
    event_type: str | None = None
    event_category: EventCategory | None = None
    source_service: str | None = None
    start_date: datetime | None = None
    end_date: datetime | None = None
    visibility: TimelineVisibility | None = None


class TimelineRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def add(self, event: TimelineEvent) -> TimelineEvent:
        self.db.add(event)
        return event

    def by_external_id(self, event_id: UUID) -> TimelineEvent | None:
        return self.db.scalar(select(TimelineEvent).where(TimelineEvent.external_event_id == event_id))

    def list_for_athlete(self, f: TimelineListFilters) -> tuple[list[TimelineEvent], int]:
        stmt = select(TimelineEvent).where(TimelineEvent.athlete_id == f.athlete_id)
        if f.event_type:
            stmt = stmt.where(TimelineEvent.event_type == f.event_type)
        if f.event_category:
            stmt = stmt.where(TimelineEvent.event_category == f.event_category)
        if f.source_service:
            stmt = stmt.where(TimelineEvent.source_service == f.source_service)
        if f.start_date:
            stmt = stmt.where(TimelineEvent.occurred_at >= f.start_date)
        if f.end_date:
            stmt = stmt.where(TimelineEvent.occurred_at <= f.end_date)
        if f.visibility:
            stmt = stmt.where(TimelineEvent.visibility == f.visibility)
        total = self.db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
        stmt = (
            stmt.order_by(desc(TimelineEvent.occurred_at), desc(TimelineEvent.created_at), desc(TimelineEvent.id))
            .offset((f.page - 1) * f.page_size)
            .limit(f.page_size)
        )
        return list(self.db.scalars(stmt)), total
