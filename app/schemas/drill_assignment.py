"""Drill assignment creation modes and lifecycle schemas."""

from datetime import date, datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core.config import settings
from app.models.enums import DrillActivityType, DrillAssignmentStatus
from app.schemas.drill import clean


class AssignmentOptions(BaseModel):
    priority: int = Field(default=3, ge=1, le=5)
    start_date: date | None = None
    due_date: date | None = None
    target_sets: int | None = Field(default=None, gt=0)
    target_repetitions: int | None = Field(default=None, gt=0)
    target_duration_minutes: int | None = Field(default=None, gt=0)
    frequency: str | None = Field(default=None, max_length=200)
    coach_notes: str | None = Field(default=None, max_length=settings.max_coach_notes_characters)
    instructions_override: str | None = Field(
        default=None, min_length=1, max_length=settings.max_drill_instructions_characters
    )

    @field_validator("frequency", "coach_notes", "instructions_override", mode="before")
    @classmethod
    def clean_optional_text(cls, value: str | None) -> str | None:
        return clean(value)

    @model_validator(mode="after")
    def validate_dates(self) -> "AssignmentOptions":
        if self.start_date and self.due_date and self.due_date < self.start_date:
            raise ValueError("due_date cannot be before start_date")
        return self


class LibraryAssignmentCreate(AssignmentOptions):
    mode: Literal["library"]
    drill_id: UUID


class ReviewAssignmentCreate(AssignmentOptions):
    mode: Literal["review"]
    source_review_id: UUID
    source_recommendation_index: int = Field(ge=0)
    mapped_drill_id: UUID | None = None
    save_to_library: bool = False

    @model_validator(mode="after")
    def validate_library_strategy(self) -> "ReviewAssignmentCreate":
        if self.mapped_drill_id and self.save_to_library:
            raise ValueError("Choose an existing drill or save a new drill, not both")
        return self


class AdHocAssignmentCreate(AssignmentOptions):
    mode: Literal["custom"]
    title: str = Field(min_length=1, max_length=settings.max_drill_title_characters)
    description: str | None = Field(default=None, max_length=settings.max_drill_description_characters)
    instructions: str = Field(min_length=1, max_length=settings.max_drill_instructions_characters)

    @field_validator("title", "description", "instructions", mode="before")
    @classmethod
    def clean_source_text(cls, value: str | None) -> str | None:
        return clean(value)


DrillAssignmentCreate = Annotated[
    LibraryAssignmentCreate | ReviewAssignmentCreate | AdHocAssignmentCreate, Field(discriminator="mode")
]


class DrillAssignmentUpdate(BaseModel):
    title_snapshot: str | None = Field(default=None, min_length=1, max_length=settings.max_drill_title_characters)
    description_snapshot: str | None = Field(default=None, max_length=settings.max_drill_description_characters)
    instructions_snapshot: str | None = Field(
        default=None, min_length=1, max_length=settings.max_drill_instructions_characters
    )
    coach_notes: str | None = Field(default=None, max_length=settings.max_coach_notes_characters)
    priority: int | None = Field(default=None, ge=1, le=5)
    start_date: date | None = None
    due_date: date | None = None
    target_sets: int | None = Field(default=None, gt=0)
    target_repetitions: int | None = Field(default=None, gt=0)
    target_duration_minutes: int | None = Field(default=None, gt=0)
    frequency: str | None = Field(default=None, max_length=200)
    completion_percentage: int | None = Field(default=None, ge=0, le=100)

    @field_validator(
        "title_snapshot",
        "description_snapshot",
        "instructions_snapshot",
        "coach_notes",
        "frequency",
        mode="before",
    )
    @classmethod
    def clean_text(cls, value: str | None) -> str | None:
        return clean(value)


class AssignmentCompleteRequest(BaseModel):
    completion_notes: str | None = Field(default=None, max_length=3000)
    actual_sets: int | None = Field(default=None, gt=0)
    actual_repetitions: int | None = Field(default=None, gt=0)
    actual_duration_minutes: int | None = Field(default=None, gt=0)


class AssignmentCancelRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=3000)


class AssignmentActivityResponse(BaseModel):
    id: UUID
    event_type: DrillActivityType
    notes: str | None
    progress_value: int | None
    occurred_at: datetime
    model_config = ConfigDict(from_attributes=True)


class DrillAssignmentResponse(BaseModel):
    id: UUID
    athlete_id: UUID
    drill_id: UUID | None
    assigned_by_user_id: UUID
    source_review_id: UUID | None
    source_recommendation_index: int | None
    title_snapshot: str
    description_snapshot: str | None
    instructions_snapshot: str
    coach_notes: str | None
    priority: int
    status: DrillAssignmentStatus
    assigned_at: datetime
    start_date: date | None
    due_date: date | None
    target_sets: int | None
    target_repetitions: int | None
    target_duration_minutes: int | None
    frequency: str | None
    completion_percentage: int
    actual_sets: int | None
    actual_repetitions: int | None
    actual_duration_minutes: int | None
    completed_at: datetime | None
    cancelled_at: datetime | None
    activities: list[AssignmentActivityResponse] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class DrillAssignmentListResponse(BaseModel):
    items: list[DrillAssignmentResponse]
    page: int
    page_size: int
    total: int
    total_pages: int
