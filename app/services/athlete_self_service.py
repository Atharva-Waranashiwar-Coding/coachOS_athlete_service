"""Athlete-facing profile, dashboard, timeline, goal, and drill use cases."""

import logging
from datetime import UTC, date, datetime
from uuid import UUID

from sqlalchemy import case, desc, func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import BadRequestError, NotFoundError, UpstreamServiceError
from app.integrations.ai_review_service import AIReviewServiceClient
from app.models.athlete import Athlete
from app.models.drill_assignment import DrillAssignment
from app.models.drill_assignment_activity import DrillAssignmentActivity
from app.models.enums import (
    ActivityNoteVisibility,
    AssignmentActorType,
    DrillActivityType,
    DrillAssignmentStatus,
    EventCategory,
    GoalCategory,
    GoalStatus,
    TimelineVisibility,
)
from app.models.goal import AthleteGoal
from app.models.timeline import TimelineEvent
from app.repositories.goal_repository import GoalListFilters, GoalRepository
from app.repositories.timeline_repository import TimelineListFilters, TimelineRepository
from app.schemas.athlete_self import (
    AthleteCompleteRequest,
    AthleteDashboardIdentity,
    AthleteDashboardResponse,
    AthleteDrillAssignmentDetail,
    AthleteDrillAssignmentListResponse,
    AthleteDrillAssignmentSummary,
    AthleteGoalListResponse,
    AthleteGoalResponse,
    AthleteProgressRequest,
    AthleteSelfProfileResponse,
    AthleteTimelineEventResponse,
    AthleteTimelineListResponse,
    DrillSummaryResponse,
    FeedbackSummaryResponse,
    GoalSummaryResponse,
)
from app.schemas.auth import CurrentAthlete
from app.services.pagination import total_pages
from app.services.progress_status_service import ProgressStatusService
from app.services.timeline_service import TimelineService

logger = logging.getLogger(__name__)

ACTIVE_ASSIGNMENT_STATUSES = {
    DrillAssignmentStatus.ASSIGNED,
    DrillAssignmentStatus.IN_PROGRESS,
}
SAFE_TIMELINE_METADATA_KEYS = {
    "category",
    "changed",
    "completion_percentage",
    "due_date",
    "priority",
    "status",
    "title",
}


class AthleteSelfService:
    """Provide self-service operations without exposing coach-owned fields."""

    def __init__(self, db: Session, ai_reviews: AIReviewServiceClient | None = None) -> None:
        self.db = db
        self.ai_reviews = ai_reviews or AIReviewServiceClient()
        self.goals = GoalRepository(db)
        self.timeline = TimelineRepository(db)
        self.timeline_service = TimelineService(db)

    def profile(self, current: CurrentAthlete) -> AthleteSelfProfileResponse:
        return AthleteSelfProfileResponse.model_validate(self._athlete(current.athlete_id))

    def goals_list(
        self,
        current: CurrentAthlete,
        *,
        page: int,
        page_size: int,
        status: GoalStatus | None,
        category: GoalCategory | None,
    ) -> AthleteGoalListResponse:
        items, total = self.goals.list_for_athlete(
            GoalListFilters(
                athlete_id=current.athlete_id,
                page=page,
                page_size=page_size,
                status=status,
                category=category,
            )
        )
        return AthleteGoalListResponse(
            items=[AthleteGoalResponse.model_validate(item) for item in items],
            page=page,
            page_size=page_size,
            total=total,
            total_pages=total_pages(total, page_size),
        )

    def timeline_list(
        self,
        current: CurrentAthlete,
        *,
        page: int,
        page_size: int,
        event_type: str | None,
        event_category: EventCategory | None,
        source_service: str | None,
        start_date: datetime | None,
        end_date: datetime | None,
    ) -> AthleteTimelineListResponse:
        items, total = self.timeline.list_for_athlete(
            TimelineListFilters(
                athlete_id=current.athlete_id,
                page=page,
                page_size=page_size,
                event_type=event_type,
                event_category=event_category,
                source_service=source_service,
                start_date=start_date,
                end_date=end_date,
                visibility=TimelineVisibility.ATHLETE_VISIBLE,
            )
        )
        return AthleteTimelineListResponse(
            items=[self._timeline_response(item) for item in items],
            page=page,
            page_size=page_size,
            total=total,
            total_pages=total_pages(total, page_size),
        )

    def assignments_list(
        self,
        current: CurrentAthlete,
        *,
        page: int,
        page_size: int,
        status: DrillAssignmentStatus | None,
        due_before: date | None,
        due_after: date | None,
        priority: int | None,
        sort_by: str | None,
        sort_order: str,
    ) -> AthleteDrillAssignmentListResponse:
        statement = select(DrillAssignment).where(DrillAssignment.athlete_id == current.athlete_id)
        if status:
            statement = statement.where(DrillAssignment.status == status)
        if due_before:
            statement = statement.where(DrillAssignment.due_date <= due_before)
        if due_after:
            statement = statement.where(DrillAssignment.due_date >= due_after)
        if priority:
            statement = statement.where(DrillAssignment.priority == priority)
        total = self.db.scalar(select(func.count()).select_from(statement.subquery())) or 0
        if sort_by:
            column = getattr(DrillAssignment, sort_by)
            statement = statement.order_by(desc(column) if sort_order == "desc" else column.asc())
        else:
            overdue = case(
                (
                    DrillAssignment.status.in_(ACTIVE_ASSIGNMENT_STATUSES)
                    & DrillAssignment.due_date.is_not(None)
                    & (DrillAssignment.due_date < date.today()),
                    0,
                ),
                else_=1,
            )
            statement = statement.order_by(
                overdue,
                DrillAssignment.due_date.asc().nulls_last(),
                DrillAssignment.assigned_at.desc(),
            )
        items = list(self.db.scalars(statement.offset((page - 1) * page_size).limit(page_size)))
        return AthleteDrillAssignmentListResponse(
            items=[self._assignment_summary(item) for item in items],
            page=page,
            page_size=page_size,
            total=total,
            total_pages=total_pages(total, page_size),
        )

    def assignment_detail(self, current: CurrentAthlete, assignment_id: UUID) -> AthleteDrillAssignmentDetail:
        return self._assignment_detail(self._assignment(current.athlete_id, assignment_id))

    def start_assignment(self, current: CurrentAthlete, assignment_id: UUID) -> AthleteDrillAssignmentDetail:
        assignment = self._assignment(current.athlete_id, assignment_id)
        if assignment.status == DrillAssignmentStatus.IN_PROGRESS:
            return self._assignment_detail(assignment)
        if assignment.status != DrillAssignmentStatus.ASSIGNED:
            raise BadRequestError("Assignment cannot be started.")
        assignment.status = DrillAssignmentStatus.IN_PROGRESS
        self._activity(assignment, current.auth_user_id, DrillActivityType.STARTED)
        self._timeline_event(assignment, "drill_started", "Drill started", current.auth_user_id)
        self._commit()
        logger.info(
            "Athlete started drill assignment",
            extra={"assignment_id": str(assignment.id), "athlete_id": str(current.athlete_id)},
        )
        return self._assignment_detail(assignment)

    def update_progress(
        self,
        current: CurrentAthlete,
        assignment_id: UUID,
        payload: AthleteProgressRequest,
    ) -> AthleteDrillAssignmentDetail:
        assignment = self._assignment(current.athlete_id, assignment_id)
        if assignment.status not in ACTIVE_ASSIGNMENT_STATUSES:
            raise BadRequestError("Only active assignments can receive progress updates.")
        if payload.completion_percentage < assignment.completion_percentage:
            raise BadRequestError("Progress cannot be decreased.")
        assignment.completion_percentage = payload.completion_percentage
        if assignment.status == DrillAssignmentStatus.ASSIGNED and payload.completion_percentage > 0:
            assignment.status = DrillAssignmentStatus.IN_PROGRESS
        self._set_actuals(assignment, payload)
        self._activity(
            assignment,
            current.auth_user_id,
            DrillActivityType.PROGRESS_UPDATED,
            notes=payload.athlete_note,
            progress=payload.completion_percentage,
            actual_sets=payload.actual_sets,
            actual_repetitions=payload.actual_repetitions,
            actual_duration_minutes=payload.actual_duration_minutes,
        )
        self._commit()
        logger.info(
            "Athlete updated drill progress",
            extra={
                "assignment_id": str(assignment.id),
                "athlete_id": str(current.athlete_id),
                "completion_percentage": payload.completion_percentage,
            },
        )
        return self._assignment_detail(assignment)

    def complete_assignment(
        self,
        current: CurrentAthlete,
        assignment_id: UUID,
        payload: AthleteCompleteRequest,
    ) -> AthleteDrillAssignmentDetail:
        assignment = self._assignment(current.athlete_id, assignment_id)
        if assignment.status == DrillAssignmentStatus.COMPLETED:
            return self._assignment_detail(assignment)
        if assignment.status == DrillAssignmentStatus.CANCELLED:
            raise BadRequestError("Cancelled assignments cannot be completed.")
        assignment.status = DrillAssignmentStatus.COMPLETED
        assignment.completion_percentage = 100
        assignment.completed_at = datetime.now(UTC)
        self._set_actuals(assignment, payload)
        self._activity(
            assignment,
            current.auth_user_id,
            DrillActivityType.COMPLETED,
            notes=payload.athlete_note,
            progress=100,
            actual_sets=payload.actual_sets,
            actual_repetitions=payload.actual_repetitions,
            actual_duration_minutes=payload.actual_duration_minutes,
        )
        self._timeline_event(assignment, "drill_completed", "Drill completed", current.auth_user_id)
        self._commit()
        logger.info(
            "Athlete completed drill assignment",
            extra={"assignment_id": str(assignment.id), "athlete_id": str(current.athlete_id)},
        )
        return self._assignment_detail(assignment)

    def dashboard(self, current: CurrentAthlete, bearer_token: str) -> AthleteDashboardResponse:
        athlete = self._athlete(current.athlete_id)
        assignments = list(
            self.db.scalars(select(DrillAssignment).where(DrillAssignment.athlete_id == current.athlete_id))
        )
        goals = list(self.db.scalars(select(AthleteGoal).where(AthleteGoal.athlete_id == current.athlete_id)))
        visible_timeline = list(
            self.db.scalars(
                select(TimelineEvent)
                .where(
                    TimelineEvent.athlete_id == current.athlete_id,
                    TimelineEvent.visibility == TimelineVisibility.ATHLETE_VISIBLE,
                )
                .order_by(
                    TimelineEvent.occurred_at.desc(),
                    TimelineEvent.created_at.desc(),
                    TimelineEvent.id.desc(),
                )
                .limit(settings.athlete_dashboard_recent_items_limit)
            )
        )
        active = [item for item in assignments if item.status in ACTIVE_ASSIGNMENT_STATUSES]
        completed = [item for item in assignments if item.status == DrillAssignmentStatus.COMPLETED]
        non_cancelled = [item for item in assignments if item.status != DrillAssignmentStatus.CANCELLED]
        overdue = [item for item in active if self._is_overdue(item)]
        completion_rate = round((len(completed) / len(non_cancelled)) * 100, 1) if non_cancelled else 0.0
        active_goals = [item for item in goals if item.status == GoalStatus.ACTIVE]
        completed_goals = [item for item in goals if item.status == GoalStatus.COMPLETED]
        recent_assignments = sorted(assignments, key=lambda item: item.assigned_at, reverse=True)[
            : settings.athlete_dashboard_recent_items_limit
        ]
        upcoming = sorted(
            [item for item in active if item.due_date is not None],
            key=lambda item: (item.due_date, -item.assigned_at.timestamp()),
        )[: settings.athlete_dashboard_recent_items_limit]
        partial_data = False
        try:
            feedback = self.ai_reviews.get_athlete_feedback_summary(bearer_token)
            feedback_summary = FeedbackSummaryResponse(
                athlete_visible_approved_count=feedback.athlete_visible_approved_count,
                latest_approved_at=feedback.latest_approved_at,
                available=True,
            )
        except UpstreamServiceError:
            partial_data = True
            feedback_summary = FeedbackSummaryResponse(
                athlete_visible_approved_count=None,
                latest_approved_at=None,
                available=False,
            )
        return AthleteDashboardResponse(
            athlete=AthleteDashboardIdentity(
                first_name=athlete.first_name,
                preferred_name=athlete.preferred_name,
                primary_position=athlete.primary_position,
            ),
            progress_status=ProgressStatusService.calculate(
                active_assignments=len(active),
                overdue_assignments=len(overdue),
                completed_assignments=len(completed),
                activated_at=current.activated_at,
            ),
            drill_summary=DrillSummaryResponse(
                active=len(active),
                in_progress=sum(item.status == DrillAssignmentStatus.IN_PROGRESS for item in assignments),
                completed=len(completed),
                overdue=len(overdue),
                completion_rate=completion_rate,
            ),
            goal_summary=GoalSummaryResponse(active=len(active_goals), completed=len(completed_goals)),
            feedback_summary=feedback_summary,
            recent_assignments=[self._assignment_summary(item) for item in recent_assignments],
            upcoming_due_assignments=[self._assignment_summary(item) for item in upcoming],
            active_goals=[
                AthleteGoalResponse.model_validate(item)
                for item in sorted(active_goals, key=lambda goal: (goal.priority, goal.target_date or date.max))[
                    : settings.athlete_dashboard_recent_items_limit
                ]
            ],
            recent_timeline=[self._timeline_response(item) for item in visible_timeline],
            partial_data=partial_data,
        )

    def _athlete(self, athlete_id: UUID) -> Athlete:
        athlete = self.db.get(Athlete, athlete_id)
        if not athlete:
            raise NotFoundError("Athlete profile is unavailable.")
        return athlete

    def _assignment(self, athlete_id: UUID, assignment_id: UUID) -> DrillAssignment:
        assignment = self.db.scalar(
            select(DrillAssignment).where(
                DrillAssignment.id == assignment_id,
                DrillAssignment.athlete_id == athlete_id,
            )
        )
        if not assignment:
            raise NotFoundError("Drill assignment not found.")
        return assignment

    @staticmethod
    def _set_actuals(assignment: DrillAssignment, payload: object) -> None:
        for field in ("actual_sets", "actual_repetitions", "actual_duration_minutes"):
            value = getattr(payload, field)
            if value is not None:
                setattr(assignment, field, value)

    def _activity(
        self,
        assignment: DrillAssignment,
        actor_user_id: UUID,
        event_type: DrillActivityType,
        *,
        notes: str | None = None,
        progress: int | None = None,
        actual_sets: int | None = None,
        actual_repetitions: int | None = None,
        actual_duration_minutes: int | None = None,
    ) -> None:
        self.db.add(
            DrillAssignmentActivity(
                assignment_id=assignment.id,
                actor_user_id=actor_user_id,
                actor_type=AssignmentActorType.ATHLETE,
                event_type=event_type,
                notes=notes,
                note_visibility=ActivityNoteVisibility.ATHLETE_VISIBLE,
                progress_value=progress,
                actual_sets=actual_sets,
                actual_repetitions=actual_repetitions,
                actual_duration_minutes=actual_duration_minutes,
            )
        )

    def _timeline_event(
        self,
        assignment: DrillAssignment,
        event_type: str,
        title: str,
        actor_user_id: UUID,
    ) -> None:
        self.timeline_service.create_event(
            athlete_id=assignment.athlete_id,
            event_type=event_type,
            event_category=EventCategory.DRILL,
            title=title,
            description=assignment.title_snapshot,
            source_entity_type="drill_assignment",
            source_entity_id=assignment.id,
            metadata={
                "title": assignment.title_snapshot,
                "priority": assignment.priority,
                "due_date": assignment.due_date.isoformat() if assignment.due_date else None,
                "completion_percentage": assignment.completion_percentage,
            },
            created_by_user_id=actor_user_id,
            visibility=TimelineVisibility.ATHLETE_VISIBLE,
        )

    @staticmethod
    def _is_overdue(assignment: DrillAssignment) -> bool:
        return (
            assignment.status in ACTIVE_ASSIGNMENT_STATUSES
            and assignment.due_date is not None
            and assignment.due_date < date.today()
        )

    @classmethod
    def _assignment_summary(cls, assignment: DrillAssignment) -> AthleteDrillAssignmentSummary:
        return AthleteDrillAssignmentSummary(
            id=assignment.id,
            title=assignment.title_snapshot,
            priority=assignment.priority,
            status=assignment.status,
            assigned_at=assignment.assigned_at,
            start_date=assignment.start_date,
            due_date=assignment.due_date,
            target_sets=assignment.target_sets,
            target_repetitions=assignment.target_repetitions,
            target_duration_minutes=assignment.target_duration_minutes,
            frequency=assignment.frequency,
            completion_percentage=assignment.completion_percentage,
            completed_at=assignment.completed_at,
            overdue=cls._is_overdue(assignment),
        )

    @classmethod
    def _assignment_detail(cls, assignment: DrillAssignment) -> AthleteDrillAssignmentDetail:
        return AthleteDrillAssignmentDetail(
            **cls._assignment_summary(assignment).model_dump(),
            description=assignment.description_snapshot,
            instructions=assignment.instructions_snapshot,
            actual_sets=assignment.actual_sets,
            actual_repetitions=assignment.actual_repetitions,
            actual_duration_minutes=assignment.actual_duration_minutes,
        )

    @staticmethod
    def _timeline_response(event: TimelineEvent) -> AthleteTimelineEventResponse:
        metadata = {
            key: value
            for key, value in event.metadata_json.items()
            if key in SAFE_TIMELINE_METADATA_KEYS and (value is None or isinstance(value, (str, int, bool)))
        }
        return AthleteTimelineEventResponse(
            id=event.id,
            event_type=event.event_type,
            event_category=event.event_category,
            title=event.title,
            description=event.description,
            occurred_at=event.occurred_at,
            metadata=metadata,
        )

    def _commit(self) -> None:
        try:
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
