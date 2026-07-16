"""Dedicated athlete-facing response and action schemas."""

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core.config import settings
from app.models.enums import (
    AthleteStatus,
    BatSide,
    DrillAssignmentStatus,
    EventCategory,
    GoalCategory,
    GoalStatus,
    Position,
    ThrowSide,
)
from app.schemas.common import PaginatedResponse


class AthleteSelfProfileResponse(BaseModel):
    id: UUID
    first_name: str
    last_name: str
    preferred_name: str | None
    primary_position: Position | None
    secondary_positions: list[Position]
    bats: BatSide | None
    throws: ThrowSide | None
    graduation_year: int | None
    school_name: str | None
    team_name: str | None
    status: AthleteStatus
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class AthleteGoalResponse(BaseModel):
    id: UUID
    title: str
    description: str | None
    category: GoalCategory
    target_date: date | None
    status: GoalStatus
    priority: int
    completed_at: datetime | None
    model_config = ConfigDict(from_attributes=True)


class AthleteGoalListResponse(PaginatedResponse[AthleteGoalResponse]):
    pass


class AthleteTimelineEventResponse(BaseModel):
    id: UUID
    event_type: str
    event_category: EventCategory
    title: str
    description: str | None
    occurred_at: datetime
    metadata: dict[str, str | int | bool | None] = Field(default_factory=dict)


class AthleteTimelineListResponse(PaginatedResponse[AthleteTimelineEventResponse]):
    pass


class AthleteDrillAssignmentSummary(BaseModel):
    id: UUID
    title: str
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
    completed_at: datetime | None
    overdue: bool


class AthleteDrillAssignmentDetail(AthleteDrillAssignmentSummary):
    description: str | None
    instructions: str
    actual_sets: int | None
    actual_repetitions: int | None
    actual_duration_minutes: int | None


class AthleteDrillAssignmentListResponse(PaginatedResponse[AthleteDrillAssignmentSummary]):
    pass


class AthleteProgressRequest(BaseModel):
    completion_percentage: int = Field(ge=0, le=99)
    actual_sets: int | None = Field(default=None, gt=0)
    actual_repetitions: int | None = Field(default=None, gt=0)
    actual_duration_minutes: int | None = Field(default=None, gt=0)
    athlete_note: str | None = Field(default=None, max_length=settings.max_athlete_note_characters)

    @field_validator("athlete_note", mode="before")
    @classmethod
    def clean_note(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None


class AthleteCompleteRequest(BaseModel):
    confirmation: bool
    actual_sets: int | None = Field(default=None, gt=0)
    actual_repetitions: int | None = Field(default=None, gt=0)
    actual_duration_minutes: int | None = Field(default=None, gt=0)
    athlete_note: str | None = Field(default=None, max_length=settings.max_athlete_note_characters)

    @model_validator(mode="after")
    def confirmed(self) -> "AthleteCompleteRequest":
        if not self.confirmation:
            raise ValueError("completion confirmation is required")
        return self

    @field_validator("athlete_note", mode="before")
    @classmethod
    def clean_note(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None


class ProgressStatusResponse(BaseModel):
    code: Literal["no_current_assignments", "needs_attention", "on_track", "getting_started"]
    label: str
    reason: str


class DrillSummaryResponse(BaseModel):
    active: int
    in_progress: int
    completed: int
    overdue: int
    completion_rate: float


class GoalSummaryResponse(BaseModel):
    active: int
    completed: int


class FeedbackSummaryResponse(BaseModel):
    athlete_visible_approved_count: int | None
    latest_approved_at: datetime | None
    available: bool


class AthleteDashboardIdentity(BaseModel):
    first_name: str
    preferred_name: str | None
    primary_position: Position | None


class AthleteDashboardResponse(BaseModel):
    athlete: AthleteDashboardIdentity
    progress_status: ProgressStatusResponse
    drill_summary: DrillSummaryResponse
    goal_summary: GoalSummaryResponse
    feedback_summary: FeedbackSummaryResponse
    recent_assignments: list[AthleteDrillAssignmentSummary]
    upcoming_due_assignments: list[AthleteDrillAssignmentSummary]
    active_goals: list[AthleteGoalResponse]
    recent_timeline: list[AthleteTimelineEventResponse]
    partial_data: bool = False
