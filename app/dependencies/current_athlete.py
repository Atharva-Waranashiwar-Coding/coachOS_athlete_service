"""Resolve an athlete profile exclusively from the authenticated athlete JWT."""

from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.db.session import get_db
from app.dependencies.auth import require_athlete
from app.models.enums import AthleteStatus
from app.repositories.athlete_repository import AthleteRepository
from app.repositories.athlete_user_link_repository import AthleteUserLinkRepository
from app.schemas.auth import CurrentAthlete, CurrentUser


def get_current_athlete(
    user: CurrentUser = Depends(require_athlete),
    db: Session = Depends(get_db),
) -> CurrentAthlete:
    link = AthleteUserLinkRepository(db).by_auth_user(user.id, active_only=True)
    if not link:
        raise NotFoundError("Athlete account link is not active.")
    athlete = AthleteRepository(db).get_by_id(link.athlete_id)
    if not athlete or athlete.status == AthleteStatus.ARCHIVED:
        raise NotFoundError("Athlete profile is unavailable.")
    return CurrentAthlete(
        auth_user_id=user.id,
        athlete_id=athlete.id,
        email=user.email,
        role=user.role,
        activated_at=link.activated_at,
    )
