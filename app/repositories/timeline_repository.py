"""Timeline persistence queries."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.models.timeline import TimelineEvent


@dataclass(frozen=True)
class TimelineListFilters:
    """Filter options for timeline listing."""

    athlete_id: UUID
    page: int
    page_size: int
    event_type: str | None = None
    start_date: datetime | None = None
    end_date: datetime | None = None


class TimelineRepository:
    """Repository for timeline event queries."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def add(self, event: TimelineEvent) -> TimelineEvent:
        """Add a timeline event to the current transaction."""
        self.db.add(event)
        return event

    def list_for_athlete(self, filters: TimelineListFilters) -> tuple[list[TimelineEvent], int]:
        """List timeline events newest first."""
        statement = select(TimelineEvent).where(TimelineEvent.athlete_id == filters.athlete_id)
        if filters.event_type:
            statement = statement.where(TimelineEvent.event_type == filters.event_type)
        if filters.start_date:
            statement = statement.where(TimelineEvent.occurred_at >= filters.start_date)
        if filters.end_date:
            statement = statement.where(TimelineEvent.occurred_at <= filters.end_date)

        total = self.db.execute(select(func.count()).select_from(statement.subquery())).scalar_one()
        statement = (
            statement.order_by(desc(TimelineEvent.occurred_at), desc(TimelineEvent.created_at))
            .offset((filters.page - 1) * filters.page_size)
            .limit(filters.page_size)
        )
        return list(self.db.execute(statement).scalars()), total
