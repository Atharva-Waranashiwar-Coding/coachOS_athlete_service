"""Goal persistence queries."""

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import asc, case, func, select
from sqlalchemy.orm import Session

from app.models.enums import GoalCategory, GoalStatus
from app.models.goal import AthleteGoal


@dataclass(frozen=True)
class GoalListFilters:
    """Filter options for goal listing."""

    athlete_id: UUID
    page: int
    page_size: int
    status: GoalStatus | None = None
    category: GoalCategory | None = None


class GoalRepository:
    """Repository for athlete goal queries."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def add(self, goal: AthleteGoal) -> AthleteGoal:
        """Add a goal to the current transaction."""
        self.db.add(goal)
        return goal

    def get_for_athlete(self, athlete_id: UUID, goal_id: UUID) -> AthleteGoal | None:
        """Return a goal belonging to an athlete."""
        statement = select(AthleteGoal).where(AthleteGoal.id == goal_id, AthleteGoal.athlete_id == athlete_id)
        return self.db.execute(statement).scalar_one_or_none()

    def list_for_athlete(self, filters: GoalListFilters) -> tuple[list[AthleteGoal], int]:
        """List goals for an athlete ordered by working priority."""
        statement = select(AthleteGoal).where(AthleteGoal.athlete_id == filters.athlete_id)
        if filters.status is not None:
            statement = statement.where(AthleteGoal.status == filters.status)
        if filters.category is not None:
            statement = statement.where(AthleteGoal.category == filters.category)

        total = self.db.execute(select(func.count()).select_from(statement.subquery())).scalar_one()
        active_order = case((AthleteGoal.status == GoalStatus.ACTIVE, 0), else_=1)
        statement = (
            statement.order_by(
                active_order, asc(AthleteGoal.priority), asc(AthleteGoal.target_date), asc(AthleteGoal.created_at)
            )
            .offset((filters.page - 1) * filters.page_size)
            .limit(filters.page_size)
        )
        return list(self.db.execute(statement).scalars()), total
