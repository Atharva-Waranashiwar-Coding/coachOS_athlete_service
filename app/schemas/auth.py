"""Authentication-related schemas consumed from JWT claims."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr

from app.models.enums import UserRole


class CurrentUser(BaseModel):
    """Authenticated user identity derived from an Auth Service JWT."""

    id: UUID
    email: EmailStr
    role: UserRole


class CurrentAthlete(BaseModel):
    """Athlete identity resolved from an active local user link."""

    auth_user_id: UUID
    athlete_id: UUID
    email: EmailStr
    role: UserRole
    activated_at: datetime | None = None
