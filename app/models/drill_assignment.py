"""Athlete drill assignment with immutable content snapshots."""

import uuid
from datetime import UTC, date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, Date, DateTime, Enum, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.enums import DrillAssignmentStatus

if TYPE_CHECKING:
    from app.models.drill_assignment_activity import DrillAssignmentActivity


class DrillAssignment(Base):
    __tablename__ = "drill_assignments"
    __table_args__ = (
        CheckConstraint("priority BETWEEN 1 AND 5", name="ck_assignment_priority"),
        CheckConstraint("completion_percentage BETWEEN 0 AND 100", name="ck_assignment_progress"),
        CheckConstraint(
            "source_review_id IS NULL = (source_recommendation_index IS NULL)", name="ck_assignment_review_source_pair"
        ),
        CheckConstraint(
            "source_recommendation_index IS NULL OR source_recommendation_index >= 0",
            name="ck_assignment_recommendation_index",
        ),
        CheckConstraint("start_date IS NULL OR due_date IS NULL OR due_date >= start_date", name="ck_assignment_dates"),
        CheckConstraint("target_sets IS NULL OR target_sets > 0", name="ck_assignment_target_sets"),
        CheckConstraint(
            "target_repetitions IS NULL OR target_repetitions > 0", name="ck_assignment_target_repetitions"
        ),
        CheckConstraint(
            "target_duration_minutes IS NULL OR target_duration_minutes > 0", name="ck_assignment_target_duration"
        ),
        CheckConstraint(
            "status != 'completed' OR (completion_percentage = 100 AND completed_at IS NOT NULL)",
            name="ck_assignment_completed_state",
        ),
        CheckConstraint(
            "status != 'cancelled' OR (cancelled_at IS NOT NULL AND completed_at IS NULL)",
            name="ck_assignment_cancelled_state",
        ),
        Index("ix_assignments_athlete", "athlete_id"),
        Index("ix_assignments_assigned_by", "assigned_by_user_id"),
        Index("ix_assignments_status", "status"),
        Index("ix_assignments_due_date", "due_date"),
        Index("ix_assignments_source_review", "source_review_id"),
        Index("ix_assignments_drill", "drill_id"),
        Index("ix_assignments_athlete_status", "athlete_id", "status"),
        Index("ix_assignments_athlete_assigned", "athlete_id", "assigned_at"),
        Index("ix_assignments_athlete_due_status", "athlete_id", "due_date", "status"),
        Index("ix_assignments_athlete_completed", "athlete_id", "completed_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    athlete_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("athletes.id"), nullable=False)
    drill_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("drills.id"))
    assigned_by_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    source_review_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    source_recommendation_index: Mapped[int | None] = mapped_column(Integer)
    title_snapshot: Mapped[str] = mapped_column(String(200), nullable=False)
    description_snapshot: Mapped[str | None] = mapped_column(Text)
    instructions_snapshot: Mapped[str] = mapped_column(Text, nullable=False)
    coach_notes: Mapped[str | None] = mapped_column(Text)
    priority: Mapped[int] = mapped_column(Integer, default=3)
    status: Mapped[DrillAssignmentStatus] = mapped_column(
        Enum(
            DrillAssignmentStatus,
            name="drill_assignment_status",
            values_callable=lambda values: [item.value for item in values],
        ),
        default=DrillAssignmentStatus.ASSIGNED,
    )
    assigned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    start_date: Mapped[date | None] = mapped_column(Date)
    due_date: Mapped[date | None] = mapped_column(Date)
    target_sets: Mapped[int | None] = mapped_column(Integer)
    target_repetitions: Mapped[int | None] = mapped_column(Integer)
    target_duration_minutes: Mapped[int | None] = mapped_column(Integer)
    frequency: Mapped[str | None] = mapped_column(String(200))
    completion_percentage: Mapped[int] = mapped_column(Integer, default=0)
    actual_sets: Mapped[int | None] = mapped_column(Integer)
    actual_repetitions: Mapped[int | None] = mapped_column(Integer)
    actual_duration_minutes: Mapped[int | None] = mapped_column(Integer)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC)
    )
    activities: Mapped[list["DrillAssignmentActivity"]] = relationship(
        back_populates="assignment", cascade="all, delete-orphan", order_by="DrillAssignmentActivity.occurred_at"
    )
