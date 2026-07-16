"""Bounded local record loads used by progress insight services."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.athlete import Athlete, CoachAthleteRelationship
from app.models.drill_assignment import DrillAssignment
from app.models.drill_assignment_activity import DrillAssignmentActivity
from app.models.enums import AthleteStatus, RelationshipStatus
from app.models.goal import AthleteGoal
from app.models.timeline import TimelineEvent


@dataclass
class InsightLocalData:
    assignments: dict[UUID, list[DrillAssignment]]
    activities: dict[UUID, list[DrillAssignmentActivity]]
    goals: dict[UUID, list[AthleteGoal]]
    timeline: dict[UUID, list[TimelineEvent]]


class InsightQueries:
    def __init__(self, db: Session) -> None:
        self.db = db

    def athletes_for_coach(self, coach_user_id: UUID, status: AthleteStatus | None = None) -> list[Athlete]:
        statement = (
            select(Athlete)
            .join(CoachAthleteRelationship)
            .options(selectinload(Athlete.secondary_position_rows))
            .where(
                CoachAthleteRelationship.coach_user_id == coach_user_id,
                CoachAthleteRelationship.status == RelationshipStatus.ACTIVE,
            )
        )
        if status:
            statement = statement.where(Athlete.status == status)
        else:
            statement = statement.where(Athlete.status != AthleteStatus.ARCHIVED)
        return list(self.db.scalars(statement.order_by(Athlete.last_name, Athlete.first_name)))

    def load(self, athlete_ids: list[UUID], query_start: datetime, end: datetime) -> InsightLocalData:
        assignments = list(
            self.db.scalars(
                select(DrillAssignment).where(
                    DrillAssignment.athlete_id.in_(athlete_ids),
                    DrillAssignment.assigned_at < end,
                )
            )
        )
        assignment_ids = [item.id for item in assignments]
        activities = (
            list(
                self.db.scalars(
                    select(DrillAssignmentActivity)
                    .where(
                        DrillAssignmentActivity.assignment_id.in_(assignment_ids),
                        DrillAssignmentActivity.occurred_at >= query_start,
                        DrillAssignmentActivity.occurred_at < end,
                    )
                    .order_by(DrillAssignmentActivity.occurred_at)
                )
            )
            if assignment_ids
            else []
        )
        goals = list(
            self.db.scalars(
                select(AthleteGoal).where(
                    AthleteGoal.athlete_id.in_(athlete_ids),
                    AthleteGoal.created_at < end,
                )
            )
        )
        timeline = list(
            self.db.scalars(
                select(TimelineEvent)
                .where(
                    TimelineEvent.athlete_id.in_(athlete_ids),
                    TimelineEvent.occurred_at >= query_start,
                    TimelineEvent.occurred_at < end,
                )
                .order_by(TimelineEvent.occurred_at.desc())
            )
        )
        assignment_athletes = {item.id: item.athlete_id for item in assignments}
        return InsightLocalData(
            assignments=self._group(assignments),
            activities=self._group(activities, lambda item: assignment_athletes[item.assignment_id]),
            goals=self._group(goals),
            timeline=self._group(timeline),
        )

    @staticmethod
    def _group(items: list, key=lambda item: item.athlete_id) -> dict[UUID, list]:
        grouped: dict[UUID, list] = {}
        for item in items:
            grouped.setdefault(key(item), []).append(item)
        return grouped
