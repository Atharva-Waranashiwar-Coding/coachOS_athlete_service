"""Athlete domain service."""

import logging
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.exceptions import BadRequestError, ForbiddenError, NotFoundError
from app.models.athlete import Athlete, AthleteSecondaryPosition, CoachAthleteRelationship
from app.models.enums import AthleteStatus, RelationshipRole, RelationshipStatus, TimelineEventType
from app.repositories.athlete_repository import AthleteListFilters, AthleteRepository
from app.schemas.athlete import AthleteCreate, AthleteDetail, AthleteListResponse, AthleteSummary, AthleteUpdate
from app.schemas.auth import CurrentUser
from app.services.pagination import total_pages
from app.services.timeline_service import TimelineService

logger = logging.getLogger(__name__)


class AthleteService:
    """Use cases for athlete profile and relationship management."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.athlete_repository = AthleteRepository(db)
        self.timeline_service = TimelineService(db)

    def create_athlete(self, payload: AthleteCreate, current_user: CurrentUser) -> AthleteDetail:
        """Create an athlete, primary coach relationship, and timeline event atomically."""
        if payload.status == AthleteStatus.ARCHIVED:
            raise BadRequestError("Create athletes as active or inactive; use archive for deletion.")

        athlete = Athlete(**payload.model_dump(exclude={"secondary_positions"}))
        athlete.secondary_position_rows = [
            AthleteSecondaryPosition(position=position) for position in payload.secondary_positions
        ]

        try:
            self.athlete_repository.add(athlete)
            self.db.flush()
            self.athlete_repository.add_relationship(
                CoachAthleteRelationship(
                    coach_user_id=current_user.id,
                    athlete_id=athlete.id,
                    relationship_role=RelationshipRole.PRIMARY_COACH,
                    status=RelationshipStatus.ACTIVE,
                )
            )
            self.timeline_service.create_event(
                athlete_id=athlete.id,
                event_type=TimelineEventType.ATHLETE_CREATED.value,
                title="Athlete created",
                source_entity_type="athlete",
                source_entity_id=athlete.id,
                metadata={"created_by_role": current_user.role.value},
                created_by_user_id=current_user.id,
            )
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        self.db.refresh(athlete)
        logger.info("Athlete created", extra={"athlete_id": str(athlete.id), "coach_user_id": str(current_user.id)})
        return AthleteDetail.model_validate(athlete)

    def list_athletes(self, filters: AthleteListFilters) -> AthleteListResponse:
        """List athletes visible to a coach."""
        items, total = self.athlete_repository.list_for_coach(filters)
        return AthleteListResponse(
            items=[AthleteSummary.model_validate(item) for item in items],
            page=filters.page,
            page_size=filters.page_size,
            total=total,
            total_pages=total_pages(total, filters.page_size),
        )

    def get_athlete(self, athlete_id: UUID, coach_user_id: UUID) -> AthleteDetail:
        """Return an athlete visible to the coach or hide it with 404."""
        athlete = self.athlete_repository.get_accessible_for_coach(athlete_id, coach_user_id)
        if athlete is None:
            raise NotFoundError("Athlete not found.")
        return AthleteDetail.model_validate(athlete)

    def update_athlete(self, athlete_id: UUID, payload: AthleteUpdate, current_user: CurrentUser) -> AthleteDetail:
        """Update an athlete when the current coach is the active primary coach."""
        athlete = self._require_primary_coach_athlete(athlete_id, current_user.id)
        data = payload.model_dump(exclude_unset=True)
        if data.get("status") == AthleteStatus.ARCHIVED:
            raise BadRequestError("Use DELETE /athletes/{athlete_id} to archive an athlete.")

        previous_injury_notes = athlete.injury_notes
        secondary_positions = data.pop("secondary_positions", None)
        updated_fields = sorted([*data.keys(), *(["secondary_positions"] if secondary_positions is not None else [])])

        try:
            for field, value in data.items():
                setattr(athlete, field, value)
            if secondary_positions is not None:
                self.athlete_repository.replace_secondary_positions(athlete, secondary_positions)

            self.timeline_service.create_event(
                athlete_id=athlete.id,
                event_type=TimelineEventType.ATHLETE_UPDATED.value,
                title="Athlete profile updated",
                source_entity_type="athlete",
                source_entity_id=athlete.id,
                metadata={"updated_fields": updated_fields},
                created_by_user_id=current_user.id,
            )
            if "injury_notes" in data and data["injury_notes"] != previous_injury_notes:
                self.timeline_service.create_event(
                    athlete_id=athlete.id,
                    event_type=TimelineEventType.INJURY_NOTE_UPDATED.value,
                    title="Injury notes updated",
                    source_entity_type="athlete",
                    source_entity_id=athlete.id,
                    metadata={"changed": True},
                    created_by_user_id=current_user.id,
                )
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        self.db.refresh(athlete)
        return AthleteDetail.model_validate(athlete)

    def archive_athlete(self, athlete_id: UUID, current_user: CurrentUser) -> None:
        """Soft-delete an athlete by archiving it."""
        athlete = self._require_primary_coach_athlete(athlete_id, current_user.id)
        now = datetime.now(UTC)

        try:
            athlete.status = AthleteStatus.ARCHIVED
            athlete.archived_at = now
            self.timeline_service.create_event(
                athlete_id=athlete.id,
                event_type=TimelineEventType.ATHLETE_ARCHIVED.value,
                title="Athlete archived",
                source_entity_type="athlete",
                source_entity_id=athlete.id,
                created_by_user_id=current_user.id,
                occurred_at=now,
            )
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

    def restore_athlete(self, athlete_id: UUID, current_user: CurrentUser) -> AthleteDetail:
        """Restore an archived athlete to active status."""
        athlete = self._require_primary_coach_athlete(athlete_id, current_user.id)
        now = datetime.now(UTC)

        try:
            athlete.status = AthleteStatus.ACTIVE
            athlete.archived_at = None
            self.timeline_service.create_event(
                athlete_id=athlete.id,
                event_type=TimelineEventType.ATHLETE_RESTORED.value,
                title="Athlete restored",
                source_entity_type="athlete",
                source_entity_id=athlete.id,
                created_by_user_id=current_user.id,
                occurred_at=now,
            )
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        self.db.refresh(athlete)
        return AthleteDetail.model_validate(athlete)

    def _require_primary_coach_athlete(self, athlete_id: UUID, coach_user_id: UUID) -> Athlete:
        athlete = self.athlete_repository.get_accessible_for_coach(athlete_id, coach_user_id)
        if athlete is None:
            raise NotFoundError("Athlete not found.")
        if not self.athlete_repository.has_primary_relationship(athlete_id, coach_user_id):
            raise ForbiddenError("Only the primary coach can modify this athlete.")
        return athlete
