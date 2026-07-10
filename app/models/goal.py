"""Athlete goal ORM model."""

import uuid
from datetime import UTC, date, datetime

from sqlalchemy import CheckConstraint, Date, DateTime, Enum, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.athlete import Athlete
from app.models.enums import GoalCategory, GoalStatus


class AthleteGoal(Base):
    """Goal attached to an athlete profile."""

    __tablename__ = "athlete_goals"
    __table_args__ = (
        CheckConstraint("priority >= 1 AND priority <= 5", name="ck_goal_priority_range"),
        Index("ix_goals_athlete_status", "athlete_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    athlete_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("athletes.id", ondelete="CASCADE"),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    category: Mapped[GoalCategory] = mapped_column(
        Enum(GoalCategory, name="goal_category", values_callable=lambda values: [item.value for item in values]),
        nullable=False,
    )
    target_date: Mapped[date | None] = mapped_column(Date)
    status: Mapped[GoalStatus] = mapped_column(
        Enum(GoalStatus, name="goal_status", values_callable=lambda values: [item.value for item in values]),
        default=GoalStatus.ACTIVE,
        nullable=False,
    )
    priority: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    athlete: Mapped[Athlete] = relationship()
