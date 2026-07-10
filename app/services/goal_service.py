"""Athlete goal domain service."""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.exceptions import ForbiddenError, NotFoundError
from app.models.enums import GoalStatus, RelationshipRole, TimelineEventType
from app.models.goal import AthleteGoal
from app.repositories.athlete_repository import AthleteRepository
from app.repositories.goal_repository import GoalListFilters, GoalRepository
from app.schemas.auth import CurrentUser
from app.schemas.goal import GoalCreate, GoalListResponse, GoalResponse, GoalUpdate
from app.services.pagination import total_pages
from app.services.timeline_service import TimelineService


class GoalService:
    """Use cases for athlete goal management."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.athlete_repository = AthleteRepository(db)
        self.goal_repository = GoalRepository(db)
        self.timeline_service = TimelineService(db)

    def create_goal(self, athlete_id: UUID, payload: GoalCreate, current_user: CurrentUser) -> GoalResponse:
        """Create a goal and timeline event atomically."""
        self._require_coach_access(athlete_id, current_user.id)
        goal = AthleteGoal(athlete_id=athlete_id, created_by_user_id=current_user.id, **payload.model_dump())

        try:
            self.goal_repository.add(goal)
            self.db.flush()
            self.timeline_service.create_event(
                athlete_id=athlete_id,
                event_type=TimelineEventType.GOAL_CREATED.value,
                title="Goal created",
                source_entity_type="goal",
                source_entity_id=goal.id,
                metadata={"goal_id": str(goal.id), "category": goal.category.value},
                created_by_user_id=current_user.id,
            )
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        self.db.refresh(goal)
        return GoalResponse.model_validate(goal)

    def list_goals(self, filters: GoalListFilters, current_user: CurrentUser) -> GoalListResponse:
        """List goals after verifying coach access."""
        self._require_coach_access(filters.athlete_id, current_user.id)
        items, total = self.goal_repository.list_for_athlete(filters)
        return GoalListResponse(
            items=items,
            page=filters.page,
            page_size=filters.page_size,
            total=total,
            total_pages=total_pages(total, filters.page_size),
        )

    def get_goal(self, athlete_id: UUID, goal_id: UUID, current_user: CurrentUser) -> GoalResponse:
        """Return one goal belonging to an accessible athlete."""
        self._require_coach_access(athlete_id, current_user.id)
        goal = self.goal_repository.get_for_athlete(athlete_id, goal_id)
        if goal is None:
            raise NotFoundError("Goal not found.")
        return GoalResponse.model_validate(goal)

    def update_goal(self, athlete_id: UUID, goal_id: UUID, payload: GoalUpdate, current_user: CurrentUser) -> GoalResponse:
        """Update a goal as primary coach and create a timeline event."""
        self._require_primary_coach(athlete_id, current_user.id)
        goal = self.goal_repository.get_for_athlete(athlete_id, goal_id)
        if goal is None:
            raise NotFoundError("Goal not found.")

        data = payload.model_dump(exclude_unset=True)
        previous_status = goal.status

        try:
            for field, value in data.items():
                setattr(goal, field, value)

            if goal.status == GoalStatus.COMPLETED and previous_status != GoalStatus.COMPLETED:
                goal.completed_at = datetime.now(UTC)
                event_type = TimelineEventType.GOAL_COMPLETED.value
                event_title = "Goal completed"
            else:
                if goal.status != GoalStatus.COMPLETED:
                    goal.completed_at = None
                event_type = TimelineEventType.GOAL_UPDATED.value
                event_title = "Goal updated"

            self.timeline_service.create_event(
                athlete_id=athlete_id,
                event_type=event_type,
                title=event_title,
                source_entity_type="goal",
                source_entity_id=goal.id,
                metadata={"goal_id": str(goal.id), "updated_fields": sorted(data.keys())},
                created_by_user_id=current_user.id,
            )
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        self.db.refresh(goal)
        return GoalResponse.model_validate(goal)

    def cancel_goal(self, athlete_id: UUID, goal_id: UUID, current_user: CurrentUser) -> None:
        """Cancel a goal instead of hard deleting it."""
        self._require_primary_coach(athlete_id, current_user.id)
        goal = self.goal_repository.get_for_athlete(athlete_id, goal_id)
        if goal is None:
            raise NotFoundError("Goal not found.")

        try:
            goal.status = GoalStatus.CANCELLED
            goal.completed_at = None
            self.timeline_service.create_event(
                athlete_id=athlete_id,
                event_type=TimelineEventType.GOAL_CANCELLED.value,
                title="Goal cancelled",
                source_entity_type="goal",
                source_entity_id=goal.id,
                metadata={"goal_id": str(goal.id)},
                created_by_user_id=current_user.id,
            )
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

    def _require_coach_access(self, athlete_id: UUID, coach_user_id: UUID) -> None:
        if self.athlete_repository.get_accessible_for_coach(athlete_id, coach_user_id) is None:
            raise NotFoundError("Athlete not found.")

    def _require_primary_coach(self, athlete_id: UUID, coach_user_id: UUID) -> None:
        relationship = self.athlete_repository.get_relationship(athlete_id, coach_user_id)
        if relationship is None:
            raise NotFoundError("Athlete not found.")
        if relationship.relationship_role != RelationshipRole.PRIMARY_COACH:
            raise ForbiddenError("Only the primary coach can modify goals.")
