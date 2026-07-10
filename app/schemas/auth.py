"""Authentication-related schemas consumed from JWT claims."""

from uuid import UUID

from pydantic import BaseModel, EmailStr

from app.models.enums import UserRole


class CurrentUser(BaseModel):
    """Authenticated user identity derived from an Auth Service JWT."""

    id: UUID
    email: EmailStr
    role: UserRole
