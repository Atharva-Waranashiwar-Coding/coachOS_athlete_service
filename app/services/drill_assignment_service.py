"""Explicit athlete drill assignment and lifecycle use cases."""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.exceptions import BadRequestError, NotFoundError
from app.integrations.ai_review_service import AIReviewServiceClient, ApprovedRecommendation
from app.models.athlete import Athlete
from app.models.drill import Drill
from app.models.drill_assignment import DrillAssignment
from app.models.drill_assignment_activity import DrillAssignmentActivity
from app.models.enums import (
    DrillActivityType,
    DrillAssignmentStatus,
    DrillCategory,
    DrillStatus,
    DrillVisibility,
    EventCategory,
    TimelineVisibility,
)
from app.repositories.drill_assignment_repository import AssignmentFilters, DrillAssignmentRepository
from app.repositories.drill_repository import DrillRepository
from app.schemas.auth import CurrentUser
from app.schemas.drill_assignment import (
    AdHocAssignmentCreate,
    AssignmentCancelRequest,
    AssignmentCompleteRequest,
    DrillAssignmentCreate,
    DrillAssignmentListResponse,
    DrillAssignmentResponse,
    DrillAssignmentUpdate,
    LibraryAssignmentCreate,
    ReviewAssignmentCreate,
)
from app.services.pagination import total_pages
from app.services.timeline_service import TimelineService


class DrillAssignmentService:
    def __init__(self, db: Session, ai_reviews: AIReviewServiceClient | None = None) -> None:
        self.db = db
        self.assignments = DrillAssignmentRepository(db)
        self.drills = DrillRepository(db)
        self.timeline = TimelineService(db)
        self.ai_reviews = ai_reviews or AIReviewServiceClient()

    def create(
        self,
        athlete: Athlete,
        payload: DrillAssignmentCreate,
        user: CurrentUser,
        bearer_token: str,
    ) -> DrillAssignmentResponse:
        recommendation: ApprovedRecommendation | None = None
        if isinstance(payload, ReviewAssignmentCreate):
            approved = self.ai_reviews.get_approved_review(payload.source_review_id, bearer_token)
            if approved.athlete_id != athlete.id:
                raise NotFoundError("Approved review not found.")
            if payload.source_recommendation_index >= len(approved.recommended_drills):
                raise NotFoundError("Approved drill recommendation not found.")
            recommendation = approved.recommended_drills[payload.source_recommendation_index]

        drill: Drill | None = None
        if isinstance(payload, LibraryAssignmentCreate):
            drill = self.drills.get_accessible(payload.drill_id, user.id)
            if not drill or drill.status != DrillStatus.ACTIVE:
                raise NotFoundError("Drill not found.")
        elif isinstance(payload, ReviewAssignmentCreate) and payload.mapped_drill_id:
            drill = self.drills.get_accessible(payload.mapped_drill_id, user.id)
            if not drill or drill.status != DrillStatus.ACTIVE:
                raise NotFoundError("Drill not found.")
        elif recommendation and isinstance(payload, ReviewAssignmentCreate) and payload.save_to_library:
            drill = Drill(
                created_by_user_id=user.id,
                title=recommendation.name,
                description=recommendation.description,
                instructions=self._recommendation_instructions(recommendation),
                category=DrillCategory.GENERAL,
                difficulty=recommendation.difficulty,
                default_frequency=recommendation.frequency,
                visibility=DrillVisibility.PRIVATE,
                status=DrillStatus.ACTIVE,
                equipment=[],
                tags=["ai-recommendation"],
            )
            self.db.add(drill)
            self.db.flush()

        source = self._snapshot_source(payload, drill, recommendation)
        assignment = DrillAssignment(
            athlete_id=athlete.id,
            drill_id=drill.id if drill else None,
            assigned_by_user_id=user.id,
            source_review_id=payload.source_review_id if isinstance(payload, ReviewAssignmentCreate) else None,
            source_recommendation_index=(
                payload.source_recommendation_index if isinstance(payload, ReviewAssignmentCreate) else None
            ),
            title_snapshot=source["title"],
            description_snapshot=source["description"],
            instructions_snapshot=payload.instructions_override or source["instructions"],
            priority=payload.priority,
            start_date=payload.start_date,
            due_date=payload.due_date,
            target_sets=payload.target_sets or (drill.default_sets if drill else None),
            target_repetitions=payload.target_repetitions or (drill.default_repetitions if drill else None),
            target_duration_minutes=payload.target_duration_minutes
            or (drill.estimated_duration_minutes if drill else None),
            frequency=payload.frequency
            or (drill.default_frequency if drill else recommendation.frequency if recommendation else None),
            coach_notes=payload.coach_notes,
        )
        self.db.add(assignment)
        self.db.flush()
        self._activity(assignment, user.id, DrillActivityType.ASSIGNED)
        self._timeline(
            assignment,
            "drill_assigned",
            "Drill assigned",
            user.id,
            TimelineVisibility.ATHLETE_VISIBLE,
            description=self._target_summary(assignment),
        )
        self._commit()
        return DrillAssignmentResponse.model_validate(assignment)

    @staticmethod
    def _recommendation_instructions(recommendation: ApprovedRecommendation) -> str:
        parts = [recommendation.description]
        if recommendation.safety_note:
            parts.append(f"Safety: {recommendation.safety_note}")
        return "\n\n".join(parts)

    def _snapshot_source(
        self,
        payload: DrillAssignmentCreate,
        drill: Drill | None,
        recommendation: ApprovedRecommendation | None,
    ) -> dict[str, str | None]:
        if drill and not isinstance(payload, ReviewAssignmentCreate):
            return {"title": drill.title, "description": drill.description, "instructions": drill.instructions}
        if recommendation:
            return {
                "title": recommendation.name,
                "description": recommendation.description,
                "instructions": self._recommendation_instructions(recommendation),
            }
        if isinstance(payload, AdHocAssignmentCreate):
            return {"title": payload.title, "description": payload.description, "instructions": payload.instructions}
        if drill:
            return {"title": drill.title, "description": drill.description, "instructions": drill.instructions}
        raise BadRequestError("Assignment source is invalid.")

    def list(self, filters: AssignmentFilters) -> DrillAssignmentListResponse:
        items, total = self.assignments.list(filters)
        return DrillAssignmentListResponse(
            items=[DrillAssignmentResponse.model_validate(item) for item in items],
            page=filters.page,
            page_size=filters.page_size,
            total=total,
            total_pages=total_pages(total, filters.page_size),
        )

    def get_model(self, athlete_id: UUID, assignment_id: UUID) -> DrillAssignment:
        assignment = self.assignments.get(athlete_id, assignment_id)
        if not assignment:
            raise NotFoundError("Drill assignment not found.")
        return assignment

    def get(self, athlete_id: UUID, assignment_id: UUID) -> DrillAssignmentResponse:
        return DrillAssignmentResponse.model_validate(self.get_model(athlete_id, assignment_id))

    def update(
        self, athlete_id: UUID, assignment_id: UUID, payload: DrillAssignmentUpdate, user: CurrentUser
    ) -> DrillAssignmentResponse:
        assignment = self.get_model(athlete_id, assignment_id)
        self._ensure_mutable(assignment)
        data = payload.model_dump(exclude_unset=True)
        start = data.get("start_date", assignment.start_date)
        due = data.get("due_date", assignment.due_date)
        if start and due and due < start:
            raise BadRequestError("due_date cannot be before start_date.")
        for field, value in data.items():
            setattr(assignment, field, value)
        if assignment.status == DrillAssignmentStatus.ASSIGNED and assignment.completion_percentage > 0:
            assignment.status = DrillAssignmentStatus.IN_PROGRESS
        self._activity(
            assignment,
            user.id,
            DrillActivityType.PROGRESS_UPDATED if "completion_percentage" in data else DrillActivityType.UPDATED,
            progress=assignment.completion_percentage,
        )
        self._commit()
        return DrillAssignmentResponse.model_validate(assignment)

    def start(self, athlete_id: UUID, assignment_id: UUID, user: CurrentUser) -> DrillAssignmentResponse:
        assignment = self.get_model(athlete_id, assignment_id)
        if assignment.status == DrillAssignmentStatus.IN_PROGRESS:
            return DrillAssignmentResponse.model_validate(assignment)
        if assignment.status != DrillAssignmentStatus.ASSIGNED:
            raise BadRequestError("Assignment cannot be started.")
        assignment.status = DrillAssignmentStatus.IN_PROGRESS
        self._activity(assignment, user.id, DrillActivityType.STARTED)
        self._timeline(assignment, "drill_started", "Drill started", user.id, TimelineVisibility.ATHLETE_VISIBLE)
        self._commit()
        return DrillAssignmentResponse.model_validate(assignment)

    def complete(
        self,
        athlete_id: UUID,
        assignment_id: UUID,
        payload: AssignmentCompleteRequest,
        user: CurrentUser,
    ) -> DrillAssignmentResponse:
        assignment = self.get_model(athlete_id, assignment_id)
        if assignment.status == DrillAssignmentStatus.COMPLETED:
            return DrillAssignmentResponse.model_validate(assignment)
        if assignment.status == DrillAssignmentStatus.CANCELLED:
            raise BadRequestError("Cancelled assignments cannot be completed.")
        assignment.status = DrillAssignmentStatus.COMPLETED
        assignment.completion_percentage = 100
        assignment.completed_at = datetime.now(UTC)
        assignment.cancelled_at = None
        assignment.actual_sets = payload.actual_sets
        assignment.actual_repetitions = payload.actual_repetitions
        assignment.actual_duration_minutes = payload.actual_duration_minutes
        self._activity(assignment, user.id, DrillActivityType.COMPLETED, notes=payload.completion_notes, progress=100)
        self._timeline(assignment, "drill_completed", "Drill completed", user.id, TimelineVisibility.ATHLETE_VISIBLE)
        self._commit()
        return DrillAssignmentResponse.model_validate(assignment)

    def cancel(
        self,
        athlete_id: UUID,
        assignment_id: UUID,
        payload: AssignmentCancelRequest,
        user: CurrentUser,
    ) -> DrillAssignmentResponse:
        assignment = self.get_model(athlete_id, assignment_id)
        if assignment.status == DrillAssignmentStatus.CANCELLED:
            return DrillAssignmentResponse.model_validate(assignment)
        if assignment.status == DrillAssignmentStatus.COMPLETED:
            raise BadRequestError("Completed assignments cannot be cancelled.")
        assignment.status = DrillAssignmentStatus.CANCELLED
        assignment.cancelled_at = datetime.now(UTC)
        self._activity(assignment, user.id, DrillActivityType.CANCELLED, notes=payload.reason)
        self._timeline(assignment, "drill_cancelled", "Drill cancelled", user.id, TimelineVisibility.COACH_ONLY)
        self._commit()
        return DrillAssignmentResponse.model_validate(assignment)

    @staticmethod
    def _ensure_mutable(assignment: DrillAssignment) -> None:
        if assignment.status in {DrillAssignmentStatus.COMPLETED, DrillAssignmentStatus.CANCELLED}:
            raise BadRequestError("Terminal assignments are read-only.")

    def _activity(
        self,
        assignment: DrillAssignment,
        actor: UUID,
        event_type: DrillActivityType,
        notes: str | None = None,
        progress: int | None = None,
    ) -> None:
        self.db.add(
            DrillAssignmentActivity(
                assignment_id=assignment.id,
                actor_user_id=actor,
                event_type=event_type,
                notes=notes,
                progress_value=progress,
            )
        )

    def _timeline(
        self,
        assignment: DrillAssignment,
        event_type: str,
        title: str,
        actor: UUID,
        visibility: TimelineVisibility,
        description: str | None = None,
    ) -> None:
        metadata: dict[str, object] = {
            "assignment_id": str(assignment.id),
            "priority": assignment.priority,
            "title": assignment.title_snapshot,
        }
        if assignment.drill_id:
            metadata["drill_id"] = str(assignment.drill_id)
        if assignment.source_review_id:
            metadata["source_review_id"] = str(assignment.source_review_id)
        if assignment.due_date:
            metadata["due_date"] = assignment.due_date.isoformat()
        self.timeline.create_event(
            athlete_id=assignment.athlete_id,
            event_type=event_type,
            event_category=EventCategory.DRILL,
            title=title,
            description=description or assignment.title_snapshot,
            source_entity_type="drill_assignment",
            source_entity_id=assignment.id,
            metadata=metadata,
            created_by_user_id=actor,
            visibility=visibility,
        )

    @staticmethod
    def _target_summary(assignment: DrillAssignment) -> str:
        targets = [
            f"{assignment.target_sets} sets" if assignment.target_sets else None,
            f"{assignment.target_repetitions} reps" if assignment.target_repetitions else None,
            f"{assignment.target_duration_minutes} minutes" if assignment.target_duration_minutes else None,
        ]
        summary = ", ".join(item for item in targets if item)
        return f"{assignment.title_snapshot}: {summary}" if summary else assignment.title_snapshot

    def _commit(self) -> None:
        try:
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
