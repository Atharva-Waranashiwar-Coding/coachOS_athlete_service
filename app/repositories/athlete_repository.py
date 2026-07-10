"""Athlete persistence queries."""

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import Select, and_, asc, desc, func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.models.athlete import Athlete, AthleteSecondaryPosition, CoachAthleteRelationship
from app.models.enums import AthleteStatus, Position, RelationshipRole, RelationshipStatus


@dataclass(frozen=True)
class AthleteListFilters:
    """Filter and sort options for athlete listing."""

    coach_user_id: UUID
    page: int
    page_size: int
    search: str | None = None
    status: AthleteStatus | None = None
    primary_position: Position | None = None
    sort_by: str = "last_name"
    sort_order: str = "asc"


class AthleteRepository:
    """Repository for athlete and relationship queries."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def add(self, athlete: Athlete) -> Athlete:
        """Add an athlete to the current transaction."""
        self.db.add(athlete)
        return athlete

    def add_relationship(self, relationship: CoachAthleteRelationship) -> CoachAthleteRelationship:
        """Add a coach-athlete relationship to the current transaction."""
        self.db.add(relationship)
        return relationship

    def get_by_id(self, athlete_id: UUID) -> Athlete | None:
        """Return an athlete by ID."""
        statement = (
            select(Athlete)
            .options(selectinload(Athlete.secondary_position_rows))
            .where(Athlete.id == athlete_id)
        )
        return self.db.execute(statement).scalar_one_or_none()

    def get_accessible_for_coach(self, athlete_id: UUID, coach_user_id: UUID) -> Athlete | None:
        """Return an athlete only when the coach has an active relationship."""
        statement = (
            select(Athlete)
            .join(CoachAthleteRelationship)
            .options(selectinload(Athlete.secondary_position_rows))
            .where(
                Athlete.id == athlete_id,
                CoachAthleteRelationship.coach_user_id == coach_user_id,
                CoachAthleteRelationship.status == RelationshipStatus.ACTIVE,
            )
        )
        return self.db.execute(statement).scalar_one_or_none()

    def get_relationship(self, athlete_id: UUID, coach_user_id: UUID) -> CoachAthleteRelationship | None:
        """Return the relationship between a coach and athlete, if one exists."""
        statement = select(CoachAthleteRelationship).where(
            CoachAthleteRelationship.athlete_id == athlete_id,
            CoachAthleteRelationship.coach_user_id == coach_user_id,
            CoachAthleteRelationship.status == RelationshipStatus.ACTIVE,
        )
        return self.db.execute(statement).scalar_one_or_none()

    def has_primary_relationship(self, athlete_id: UUID, coach_user_id: UUID) -> bool:
        """Return true when the coach is the active primary coach."""
        relationship = self.get_relationship(athlete_id, coach_user_id)
        return relationship is not None and relationship.relationship_role == RelationshipRole.PRIMARY_COACH

    def list_for_coach(self, filters: AthleteListFilters) -> tuple[list[Athlete], int]:
        """List athletes visible to a coach with filters and pagination."""
        statement = self._base_list_statement(filters)
        count_statement = select(func.count()).select_from(statement.subquery())
        total = self.db.execute(count_statement).scalar_one()

        sort_column = {
            "first_name": Athlete.first_name,
            "last_name": Athlete.last_name,
            "created_at": Athlete.created_at,
            "updated_at": Athlete.updated_at,
        }[filters.sort_by]
        order_by = desc(sort_column) if filters.sort_order == "desc" else asc(sort_column)

        paged = (
            statement.options(selectinload(Athlete.secondary_position_rows))
            .order_by(order_by, asc(Athlete.id))
            .offset((filters.page - 1) * filters.page_size)
            .limit(filters.page_size)
        )
        return list(self.db.execute(paged).scalars().unique()), total

    def replace_secondary_positions(self, athlete: Athlete, positions: list[Position]) -> None:
        """Replace secondary position rows for an athlete."""
        athlete.secondary_position_rows = [
            AthleteSecondaryPosition(athlete_id=athlete.id, position=position)
            for position in positions
        ]

    def _base_list_statement(self, filters: AthleteListFilters) -> Select[tuple[Athlete]]:
        statement = (
            select(Athlete)
            .join(CoachAthleteRelationship)
            .where(
                CoachAthleteRelationship.coach_user_id == filters.coach_user_id,
                CoachAthleteRelationship.status == RelationshipStatus.ACTIVE,
            )
        )

        conditions = []
        if filters.status is None:
            conditions.append(Athlete.status != AthleteStatus.ARCHIVED)
        else:
            conditions.append(Athlete.status == filters.status)

        if filters.primary_position is not None:
            conditions.append(Athlete.primary_position == filters.primary_position)

        if filters.search:
            pattern = f"%{filters.search.strip()}%"
            conditions.append(
                or_(
                    Athlete.first_name.ilike(pattern),
                    Athlete.last_name.ilike(pattern),
                    Athlete.preferred_name.ilike(pattern),
                )
            )

        if conditions:
            statement = statement.where(and_(*conditions))

        return statement
