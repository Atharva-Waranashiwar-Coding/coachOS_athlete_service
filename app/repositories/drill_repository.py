"""Persistence queries for coach drill libraries."""

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import asc, desc, func, or_, select
from sqlalchemy.orm import Session

from app.models.drill import Drill
from app.models.enums import DrillCategory, DrillDifficulty, DrillStatus, DrillVisibility


@dataclass(frozen=True)
class DrillFilters:
    user_id: UUID
    page: int
    page_size: int
    search: str | None = None
    category: DrillCategory | None = None
    difficulty: DrillDifficulty | None = None
    status: DrillStatus | None = None
    tag: str | None = None
    sort_by: str = "updated_at"
    sort_order: str = "desc"


class DrillRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def add(self, drill: Drill) -> Drill:
        self.db.add(drill)
        return drill

    def get_accessible(self, drill_id: UUID, user_id: UUID) -> Drill | None:
        return self.db.scalar(
            select(Drill).where(
                Drill.id == drill_id,
                or_(
                    (Drill.created_by_user_id == user_id) & (Drill.visibility == DrillVisibility.PRIVATE),
                    Drill.visibility == DrillVisibility.SYSTEM,
                ),
            )
        )

    def list(self, filters: DrillFilters) -> tuple[list[Drill], int]:
        statement = select(Drill).where(
            or_(
                (Drill.created_by_user_id == filters.user_id) & (Drill.visibility == DrillVisibility.PRIVATE),
                Drill.visibility == DrillVisibility.SYSTEM,
            )
        )
        status = filters.status or DrillStatus.ACTIVE
        statement = statement.where(Drill.status == status)
        if filters.search:
            term = f"%{filters.search.strip().lower()}%"
            statement = statement.where(func.lower(Drill.title).like(term))
        if filters.category:
            statement = statement.where(Drill.category == filters.category)
        if filters.difficulty:
            statement = statement.where(Drill.difficulty == filters.difficulty)
        if filters.tag:
            statement = statement.where(Drill.tags.contains([filters.tag.lower()]))
        total = self.db.scalar(select(func.count()).select_from(statement.subquery())) or 0
        column = getattr(Drill, filters.sort_by)
        items = list(
            self.db.scalars(
                statement.order_by(desc(column) if filters.sort_order == "desc" else asc(column))
                .offset((filters.page - 1) * filters.page_size)
                .limit(filters.page_size)
            )
        )
        return items, total
