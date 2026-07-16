"""Coach-controlled athlete account linking and access lifecycle."""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, NotFoundError
from app.integrations.auth_service import AuthServiceClient
from app.models.athlete import Athlete
from app.models.athlete_user_link import AthleteUserLink
from app.models.enums import AthleteUserLinkStatus
from app.repositories.athlete_user_link_repository import AthleteUserLinkRepository
from app.schemas.athlete_invitation import AthleteInvitationRequest, AthleteInvitationResponse
from app.schemas.auth import CurrentUser


class AthleteInvitationService:
    def __init__(self, db: Session, auth: AuthServiceClient | None = None) -> None:
        self.db = db
        self.auth = auth or AuthServiceClient()
        self.links = AthleteUserLinkRepository(db)

    def invite(
        self, athlete: Athlete, payload: AthleteInvitationRequest, user: CurrentUser
    ) -> AthleteInvitationResponse:
        existing = self.links.by_athlete(athlete.id, current_only=True)
        if existing:
            raise ConflictError("Athlete already has a pending or active account link.")
        auth_result = self.auth.create_athlete_user(payload.email, athlete.id, user.id)
        status = AthleteUserLinkStatus.ACTIVE if auth_result.user_status == "active" else AthleteUserLinkStatus.INVITED
        now = datetime.now(UTC)
        link = AthleteUserLink(
            athlete_id=athlete.id,
            auth_user_id=auth_result.auth_user_id,
            invitation_email=str(payload.email).lower(),
            status=status,
            invited_by_user_id=user.id,
            invited_at=now,
            activated_at=now if status == AthleteUserLinkStatus.ACTIVE else None,
        )
        self.links.add(link)
        self.db.commit()
        self.db.refresh(link)
        return self._response(link, auth_result.development_invitation_url)

    def get(self, athlete_id: UUID) -> AthleteInvitationResponse:
        link = self.links.by_athlete(athlete_id)
        if not link:
            raise NotFoundError("Athlete invitation not found.")
        return self._response(link)

    def resend(
        self, athlete: Athlete, payload: AthleteInvitationRequest, user: CurrentUser
    ) -> AthleteInvitationResponse:
        link = self.links.by_athlete(athlete.id, current_only=True)
        if not link or link.status != AthleteUserLinkStatus.INVITED:
            raise ConflictError("Only pending invitations can be resent.")
        if link.invitation_email != str(payload.email).lower():
            raise ConflictError("Invitation email must match the pending account.")
        result = self.auth.resend(link.auth_user_id, payload.email, athlete.id, user.id)
        link.invited_at = datetime.now(UTC)
        link.invited_by_user_id = user.id
        self.db.commit()
        return self._response(link, result.development_invitation_url)

    def disable(self, athlete_id: UUID) -> None:
        link = self.links.by_athlete(athlete_id, current_only=True)
        if not link:
            raise NotFoundError("Athlete account link not found.")
        self.auth.disable(link.auth_user_id)
        link.status = AthleteUserLinkStatus.DISABLED
        link.disabled_at = datetime.now(UTC)
        self.db.commit()

    def activate(self, auth_user_id: UUID) -> AthleteUserLink:
        link = self.links.by_auth_user(auth_user_id)
        if not link or link.status != AthleteUserLinkStatus.INVITED:
            raise NotFoundError("Pending athlete account link not found.")
        link.status = AthleteUserLinkStatus.ACTIVE
        link.activated_at = datetime.now(UTC)
        link.disabled_at = None
        self.db.commit()
        self.db.refresh(link)
        return link

    @staticmethod
    def _response(link: AthleteUserLink, development_url: str | None = None) -> AthleteInvitationResponse:
        return AthleteInvitationResponse(
            athlete_id=link.athlete_id,
            auth_user_id=link.auth_user_id,
            email=link.invitation_email,
            status=link.status,
            invited_at=link.invited_at,
            activated_at=link.activated_at,
            disabled_at=link.disabled_at,
            development_invitation_url=development_url,
        )
