from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.enums import EventCategory, TimelineVisibility
from app.schemas.common import PaginatedResponse


class TimelineIngestionRequest(BaseModel):
    event_id: UUID
    athlete_id: UUID
    event_type: str = Field(min_length=1, max_length=100)
    event_category: EventCategory
    title: str = Field(min_length=1, max_length=200)
    description: str | None = None
    source_service: str = Field(min_length=1, max_length=100)
    source_entity_type: str | None = Field(default=None, max_length=100)
    source_entity_id: str | None = Field(default=None, max_length=255)
    actor_user_id: UUID | None = None
    occurred_at: datetime
    metadata: dict[str, Any] = Field(default_factory=dict)
    schema_version: int = Field(default=1, ge=1, le=1)
    visibility: TimelineVisibility
    model_config = ConfigDict(extra="forbid")

    @field_validator("title", "event_type", "source_service")
    @classmethod
    def nonempty(cls, value: str) -> str:
        if not (value := value.strip()):
            raise ValueError("value cannot be blank")
        return value

    @model_validator(mode="after")
    def timezone_required(self) -> "TimelineIngestionRequest":
        if self.occurred_at.tzinfo is None:
            raise ValueError("occurred_at must include a timezone")
        return self


class TimelineEventResponse(BaseModel):
    id: UUID
    athlete_id: UUID
    event_type: str
    event_category: EventCategory
    title: str
    description: str | None
    source_service: str
    source_entity_type: str | None
    source_entity_id: str | None
    actor_user_id: UUID | None
    occurred_at: datetime
    metadata: dict[str, Any] = Field(default_factory=dict, validation_alias="metadata_json")
    schema_version: int
    visibility: TimelineVisibility
    created_at: datetime
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class TimelineListResponse(PaginatedResponse[TimelineEventResponse]):
    pass
