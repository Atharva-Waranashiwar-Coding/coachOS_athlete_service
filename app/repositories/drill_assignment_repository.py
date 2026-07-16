"""Persistence queries for athlete drill assignments."""

from dataclasses import dataclass
from datetime import date
from uuid import UUID

from sqlalchemy import asc, desc, func, select
from sqlalchemy.orm import Session

from app.models.drill import Drill
from app.models.drill_assignment import DrillAssignment
from app.models.enums import DrillAssignmentStatus, DrillCategory


@dataclass(frozen=True)
class AssignmentFilters:
    athlete_id: UUID
    page: int
    page_size: int
    status: DrillAssignmentStatus | None = None
    category: DrillCategory | None = None
    priority: int | None = None
    due_before: date | None = None
    due_after: date | None = None
    source_review_id: UUID | None = None
    sort_by: str = "assigned_at"
    sort_order: str = "desc"


class DrillAssignmentRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def add(self, assignment: DrillAssignment) -> DrillAssignment:
        self.db.add(assignment)
        return assignment

    def get(self, athlete_id: UUID, assignment_id: UUID) -> DrillAssignment | None:
        return self.db.scalar(
            select(DrillAssignment).where(DrillAssignment.id == assignment_id, DrillAssignment.athlete_id == athlete_id)
        )

    def list(self, filters: AssignmentFilters) -> tuple[list[DrillAssignment], int]:
        statement = select(DrillAssignment).where(DrillAssignment.athlete_id == filters.athlete_id)
        if filters.status:
            statement = statement.where(DrillAssignment.status == filters.status)
        if filters.category:
            statement = statement.join(Drill, Drill.id == DrillAssignment.drill_id).where(
                Drill.category == filters.category
            )
        if filters.priority:
            statement = statement.where(DrillAssignment.priority == filters.priority)
        if filters.due_before:
            statement = statement.where(DrillAssignment.due_date <= filters.due_before)
        if filters.due_after:
            statement = statement.where(DrillAssignment.due_date >= filters.due_after)
        if filters.source_review_id:
            statement = statement.where(DrillAssignment.source_review_id == filters.source_review_id)
        total = self.db.scalar(select(func.count()).select_from(statement.subquery())) or 0
        column = getattr(DrillAssignment, filters.sort_by)
        return (
            list(
                self.db.scalars(
                    statement.order_by(desc(column) if filters.sort_order == "desc" else asc(column))
                    .offset((filters.page - 1) * filters.page_size)
                    .limit(filters.page_size)
                )
            ),
            total,
        )
