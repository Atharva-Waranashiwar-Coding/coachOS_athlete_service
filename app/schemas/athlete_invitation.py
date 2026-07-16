"""Coach-facing athlete account invitation schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr

from app.models.enums import AthleteUserLinkStatus


class AthleteInvitationRequest(BaseModel):
    email: EmailStr
    model_config = ConfigDict(extra="forbid")


class AthleteInvitationResponse(BaseModel):
    athlete_id: UUID
    auth_user_id: UUID
    email: EmailStr
    status: AthleteUserLinkStatus
    invited_at: datetime
    activated_at: datetime | None
    disabled_at: datetime | None
    development_invitation_url: str | None = None
    model_config = ConfigDict(from_attributes=True)
