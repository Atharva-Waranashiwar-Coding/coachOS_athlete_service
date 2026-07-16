"""Auth Service callback for athlete link activation."""

from uuid import UUID

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.core.exceptions import ForbiddenError
from app.db.session import get_db
from app.dependencies.internal_auth import InternalServiceIdentity, require_internal_service
from app.services.athlete_invitation_service import AthleteInvitationService

router = APIRouter(prefix="/athlete-user-links", tags=["internal-athlete-links"])


@router.post("/{auth_user_id}/activate", status_code=status.HTTP_204_NO_CONTENT)
def activate_link(
    auth_user_id: UUID,
    identity: InternalServiceIdentity = Depends(require_internal_service),
    db: Session = Depends(get_db),
) -> Response:
    if identity.name != "auth-service":
        raise ForbiddenError("Only Auth Service may activate athlete account links.")
    AthleteInvitationService(db).activate(auth_user_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
