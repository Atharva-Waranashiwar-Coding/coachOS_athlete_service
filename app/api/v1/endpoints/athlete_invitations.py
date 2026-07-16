"""Primary-coach athlete account invitation endpoints."""

from uuid import UUID

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies.athlete_access import require_primary_coach_access
from app.dependencies.auth import require_coach
from app.models.athlete import Athlete
from app.schemas.athlete_invitation import AthleteInvitationRequest, AthleteInvitationResponse
from app.schemas.auth import CurrentUser
from app.services.athlete_invitation_service import AthleteInvitationService

router = APIRouter(prefix="/athletes/{athlete_id}", tags=["athlete-access"])


@router.post("/invite", response_model=AthleteInvitationResponse, status_code=status.HTTP_201_CREATED)
def invite_athlete(
    payload: AthleteInvitationRequest,
    athlete: Athlete = Depends(require_primary_coach_access),
    user: CurrentUser = Depends(require_coach),
    db: Session = Depends(get_db),
) -> AthleteInvitationResponse:
    return AthleteInvitationService(db).invite(athlete, payload, user)


@router.get("/invite", response_model=AthleteInvitationResponse)
def get_invitation(
    athlete_id: UUID,
    _: Athlete = Depends(require_primary_coach_access),
    db: Session = Depends(get_db),
) -> AthleteInvitationResponse:
    return AthleteInvitationService(db).get(athlete_id)


@router.post("/invite/resend", response_model=AthleteInvitationResponse)
def resend_invitation(
    payload: AthleteInvitationRequest,
    athlete: Athlete = Depends(require_primary_coach_access),
    user: CurrentUser = Depends(require_coach),
    db: Session = Depends(get_db),
) -> AthleteInvitationResponse:
    return AthleteInvitationService(db).resend(athlete, payload, user)


@router.post("/access/disable", status_code=status.HTTP_204_NO_CONTENT)
def disable_access(
    athlete_id: UUID,
    _: Athlete = Depends(require_primary_coach_access),
    db: Session = Depends(get_db),
) -> Response:
    AthleteInvitationService(db).disable(athlete_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
