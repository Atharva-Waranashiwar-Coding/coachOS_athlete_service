"""Reusable coach-owned drill library model."""

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Enum, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.models.enums import DrillCategory, DrillDifficulty, DrillStatus, DrillVisibility

Json = JSON().with_variant(JSONB, "postgresql")


class Drill(Base):
    __tablename__ = "drills"
    __table_args__ = (
        Index("ix_drills_created_by", "created_by_user_id"),
        Index("ix_drills_category", "category"),
        Index("ix_drills_difficulty", "difficulty"),
        Index("ix_drills_status", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    instructions: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[DrillCategory] = mapped_column(
        Enum(DrillCategory, name="drill_category", values_callable=lambda values: [item.value for item in values])
    )
    sport: Mapped[str] = mapped_column(String(50), default="baseball")
    difficulty: Mapped[DrillDifficulty] = mapped_column(
        Enum(DrillDifficulty, name="drill_difficulty", values_callable=lambda values: [item.value for item in values])
    )
    equipment: Mapped[list[Any]] = mapped_column(Json, default=list)
    estimated_duration_minutes: Mapped[int | None] = mapped_column(Integer)
    default_sets: Mapped[int | None] = mapped_column(Integer)
    default_repetitions: Mapped[int | None] = mapped_column(Integer)
    default_frequency: Mapped[str | None] = mapped_column(String(200))
    tags: Mapped[list[Any]] = mapped_column(Json, default=list)
    video_url: Mapped[str | None] = mapped_column(String(2000))
    visibility: Mapped[DrillVisibility] = mapped_column(
        Enum(DrillVisibility, name="drill_visibility", values_callable=lambda values: [item.value for item in values]),
        default=DrillVisibility.PRIVATE,
    )
    status: Mapped[DrillStatus] = mapped_column(
        Enum(DrillStatus, name="drill_status", values_callable=lambda values: [item.value for item in values]),
        default=DrillStatus.ACTIVE,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC)
    )
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
