"""Athlete request and response schemas."""

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

from app.core.config import settings
from app.models.enums import AthleteStatus, BatSide, Position, ThrowSide
from app.schemas.common import PaginatedResponse


def _strip_optional(value: str | None) -> str | None:
    """Trim optional strings and convert blanks to None."""
    if value is None:
        return None
    value = value.strip()
    return value or None


class AthleteBase(BaseModel):
    """Shared athlete fields."""

    first_name: str | None = Field(default=None, max_length=100)
    last_name: str | None = Field(default=None, max_length=100)
    preferred_name: str | None = Field(default=None, max_length=100)
    date_of_birth: date | None = None
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=50)
    primary_position: Position | None = None
    secondary_positions: list[Position] = Field(default_factory=list)
    bats: BatSide | None = None
    throws: ThrowSide | None = None
    graduation_year: int | None = None
    school_name: str | None = Field(default=None, max_length=200)
    team_name: str | None = Field(default=None, max_length=200)
    height_inches: int | None = Field(default=None, gt=0, le=100)
    weight_pounds: int | None = Field(default=None, gt=0, le=500)
    injury_notes: str | None = None
    general_notes: str | None = None

    @field_validator(
        "first_name",
        "last_name",
        "preferred_name",
        "phone",
        "school_name",
        "team_name",
        mode="before",
    )
    @classmethod
    def strip_strings(cls, value: str | None) -> str | None:
        """Trim incoming string values."""
        return _strip_optional(value)

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value: str | None) -> str | None:
        """Normalize email addresses to lowercase."""
        stripped = _strip_optional(value)
        return stripped.lower() if stripped else None

    @field_validator("date_of_birth")
    @classmethod
    def date_of_birth_not_future(cls, value: date | None) -> date | None:
        """Reject future birth dates."""
        if value and value > date.today():
            raise ValueError("date_of_birth cannot be in the future")
        return value

    @field_validator("graduation_year")
    @classmethod
    def graduation_year_in_range(cls, value: int | None) -> int | None:
        """Validate graduation year against configured bounds."""
        if value is not None and not settings.graduation_year_min <= value <= settings.graduation_year_max:
            raise ValueError(
                f"graduation_year must be between {settings.graduation_year_min} and {settings.graduation_year_max}"
            )
        return value

    @field_validator("secondary_positions")
    @classmethod
    def unique_secondary_positions(cls, value: list[Position]) -> list[Position]:
        """Deduplicate secondary positions while preserving order."""
        return list(dict.fromkeys(value))


class AthleteCreate(AthleteBase):
    """Request body for athlete creation."""

    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    status: AthleteStatus = AthleteStatus.ACTIVE

    @model_validator(mode="after")
    def validate_required_names(self) -> "AthleteCreate":
        """Reject names that become blank after trimming."""
        if not self.first_name.strip() or not self.last_name.strip():
            raise ValueError("first_name and last_name are required")
        return self


class AthleteUpdate(AthleteBase):
    """Partial update body for athlete profile changes."""

    status: AthleteStatus | None = None


class AthleteSummary(BaseModel):
    """Athlete list response that excludes sensitive notes."""

    id: UUID
    first_name: str
    last_name: str
    preferred_name: str | None
    email: EmailStr | None
    primary_position: Position | None
    secondary_positions: list[Position]
    graduation_year: int | None
    school_name: str | None
    team_name: str | None
    status: AthleteStatus
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AthleteDetail(AthleteSummary):
    """Full athlete profile response."""

    date_of_birth: date | None
    phone: str | None
    bats: BatSide | None
    throws: ThrowSide | None
    height_inches: int | None
    weight_pounds: int | None
    injury_notes: str | None
    general_notes: str | None
    archived_at: datetime | None


class AthleteListResponse(PaginatedResponse[AthleteSummary]):
    """Paginated athlete list response."""
