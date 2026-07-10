"""Goal request and response schemas."""

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.enums import GoalCategory, GoalStatus
from app.schemas.common import PaginatedResponse


def _strip_required(value: str) -> str:
    """Trim required strings and reject blanks."""
    stripped = value.strip()
    if not stripped:
        raise ValueError("value cannot be blank")
    return stripped


class GoalCreate(BaseModel):
    """Request body for goal creation."""

    title: str = Field(min_length=1, max_length=200)
    description: str | None = None
    category: GoalCategory
    target_date: date | None = None
    priority: int = Field(default=3, ge=1, le=5)

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str) -> str:
        """Trim and validate title."""
        return _strip_required(value)

    @field_validator("description", mode="before")
    @classmethod
    def strip_description(cls, value: str | None) -> str | None:
        """Trim optional description."""
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class GoalUpdate(BaseModel):
    """Partial update body for goals."""

    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    category: GoalCategory | None = None
    target_date: date | None = None
    status: GoalStatus | None = None
    priority: int | None = Field(default=None, ge=1, le=5)

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str | None) -> str | None:
        """Trim and validate title."""
        return _strip_required(value) if value is not None else None


class GoalResponse(BaseModel):
    """Goal response schema."""

    id: UUID
    athlete_id: UUID
    title: str
    description: str | None
    category: GoalCategory
    target_date: date | None
    status: GoalStatus
    priority: int
    created_by_user_id: UUID
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


class GoalListResponse(PaginatedResponse[GoalResponse]):
    """Paginated goal response."""
