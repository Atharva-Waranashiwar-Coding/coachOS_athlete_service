"""Athlete access dependencies for future endpoint reuse."""

from uuid import UUID

from fastapi import Depends, Path
from sqlalchemy.orm import Session

from app.core.exceptions import ForbiddenError, NotFoundError
from app.db.session import get_db
from app.dependencies.auth import require_coach
from app.models.athlete import Athlete
from app.models.enums import RelationshipRole
from app.repositories.athlete_repository import AthleteRepository
from app.schemas.auth import CurrentUser


def get_accessible_athlete(
    athlete_id: UUID = Path(...),
    current_user: CurrentUser = Depends(require_coach),
    db: Session = Depends(get_db),
) -> Athlete:
    """Return the athlete if the coach has active access, otherwise raise 404."""
    athlete = AthleteRepository(db).get_accessible_for_coach(athlete_id, current_user.id)
    if athlete is None:
        raise NotFoundError("Athlete not found.")
    return athlete


def require_primary_coach_access(
    athlete_id: UUID = Path(...),
    current_user: CurrentUser = Depends(require_coach),
    db: Session = Depends(get_db),
) -> Athlete:
    """Return the athlete only when the coach is the active primary coach."""
    repository = AthleteRepository(db)
    athlete = repository.get_accessible_for_coach(athlete_id, current_user.id)
    if athlete is None:
        raise NotFoundError("Athlete not found.")
    relationship = repository.get_relationship(athlete_id, current_user.id)
    if relationship is None or relationship.relationship_role != RelationshipRole.PRIMARY_COACH:
        raise ForbiddenError("Only the primary coach can modify this athlete.")
    return athlete
