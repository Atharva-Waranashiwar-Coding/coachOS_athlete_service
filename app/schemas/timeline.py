"""Timeline response schemas."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import PaginatedResponse


class TimelineEventResponse(BaseModel):
    """Timeline event response schema."""

    id: UUID
    athlete_id: UUID
    event_type: str
    title: str
    description: str | None
    source_service: str
    source_entity_type: str | None
    source_entity_id: str | None
    metadata: dict[str, Any] = Field(default_factory=dict, validation_alias="metadata_json")
    occurred_at: datetime
    created_by_user_id: UUID | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class TimelineListResponse(PaginatedResponse[TimelineEventResponse]):
    """Paginated timeline response."""
