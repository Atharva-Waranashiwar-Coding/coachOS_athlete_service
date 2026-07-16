"""Canonical athlete timeline ORM model."""

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, CheckConstraint, DateTime, Enum, ForeignKey, Index, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.athlete import Athlete
from app.models.enums import EventCategory, TimelineVisibility

Json = JSON().with_variant(JSONB, "postgresql")


class TimelineEvent(Base):
    """Append-only canonical athlete timeline event."""

    __tablename__ = "timeline_events"
    __table_args__ = (
        CheckConstraint("schema_version > 0", name="ck_timeline_schema_version_positive"),
        CheckConstraint("length(trim(title)) > 0", name="ck_timeline_title_nonempty"),
        CheckConstraint("length(trim(source_service)) > 0", name="ck_timeline_source_service_nonempty"),
        CheckConstraint("length(trim(event_type)) > 0", name="ck_timeline_event_type_nonempty"),
        Index("ix_timeline_athlete_occurred_created", "athlete_id", text("occurred_at DESC"), text("created_at DESC")),
        Index("ix_timeline_athlete_category", "athlete_id", "event_category"),
        Index("ix_timeline_athlete_visibility_occurred", "athlete_id", "visibility", "occurred_at"),
        Index("ix_timeline_athlete_event_type", "athlete_id", "event_type"),
        Index("ix_timeline_source_entity", "source_entity_type", "source_entity_id"),
        Index(
            "ix_timeline_external_event_id",
            "external_event_id",
            unique=True,
            postgresql_where=text("external_event_id IS NOT NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    external_event_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    athlete_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("athletes.id", ondelete="CASCADE"), nullable=False
    )
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    event_category: Mapped[EventCategory] = mapped_column(
        Enum(EventCategory, name="timeline_event_category"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    source_service: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    source_entity_type: Mapped[str | None] = mapped_column(String(100))
    source_entity_id: Mapped[str | None] = mapped_column(String(255))
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    metadata_json: Mapped[dict[str, Any]] = mapped_column("metadata", Json, default=dict, nullable=False)
    schema_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    visibility: Mapped[TimelineVisibility] = mapped_column(
        Enum(TimelineVisibility, name="timeline_visibility"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    athlete: Mapped[Athlete] = relationship()
