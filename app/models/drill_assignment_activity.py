"""Assignment-specific lifecycle audit records."""

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.enums import ActivityNoteVisibility, AssignmentActorType, DrillActivityType

if TYPE_CHECKING:
    from app.models.drill_assignment import DrillAssignment


class DrillAssignmentActivity(Base):
    __tablename__ = "drill_assignment_activities"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    assignment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("drill_assignments.id", ondelete="CASCADE"), nullable=False, index=True
    )
    actor_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    actor_type: Mapped[AssignmentActorType] = mapped_column(
        Enum(
            AssignmentActorType,
            name="assignment_actor_type",
            values_callable=lambda values: [item.value for item in values],
        ),
        default=AssignmentActorType.COACH,
        nullable=False,
    )
    event_type: Mapped[DrillActivityType] = mapped_column(
        Enum(
            DrillActivityType,
            name="drill_activity_type",
            values_callable=lambda values: [item.value for item in values],
        )
    )
    notes: Mapped[str | None] = mapped_column(Text)
    note_visibility: Mapped[ActivityNoteVisibility] = mapped_column(
        Enum(
            ActivityNoteVisibility,
            name="activity_note_visibility",
            values_callable=lambda values: [item.value for item in values],
        ),
        default=ActivityNoteVisibility.COACH_ONLY,
        nullable=False,
    )
    progress_value: Mapped[int | None] = mapped_column(Integer)
    actual_sets: Mapped[int | None] = mapped_column(Integer)
    actual_repetitions: Mapped[int | None] = mapped_column(Integer)
    actual_duration_minutes: Mapped[int | None] = mapped_column(Integer)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    assignment: Mapped["DrillAssignment"] = relationship(back_populates="activities")
