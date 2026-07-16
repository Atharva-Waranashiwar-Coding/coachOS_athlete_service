"""Drill library request and response schemas."""

import re
from datetime import datetime
from uuid import UUID

from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field, field_validator

from app.core.config import settings
from app.models.enums import DrillCategory, DrillDifficulty, DrillStatus, DrillVisibility

TAG = re.compile(r"<[^>]+>")


def clean(value: str | None) -> str | None:
    if value is None:
        return None
    return " ".join(TAG.sub("", value).split())


def normalize_items(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for item in values:
        normalized = (clean(item) or "").lower()
        if normalized and normalized not in seen:
            seen.add(normalized)
            result.append(normalized)
    return result


class DrillCreate(BaseModel):
    title: str = Field(min_length=1, max_length=settings.max_drill_title_characters)
    description: str | None = Field(default=None, max_length=settings.max_drill_description_characters)
    instructions: str = Field(min_length=1, max_length=settings.max_drill_instructions_characters)
    category: DrillCategory
    difficulty: DrillDifficulty
    equipment: list[str] = Field(default_factory=list)
    estimated_duration_minutes: int | None = Field(default=None, gt=0)
    default_sets: int | None = Field(default=None, gt=0)
    default_repetitions: int | None = Field(default=None, gt=0)
    default_frequency: str | None = Field(default=None, max_length=200)
    tags: list[str] = Field(default_factory=list)
    video_url: AnyHttpUrl | None = None

    @field_validator("title", "description", "instructions", "default_frequency", mode="before")
    @classmethod
    def clean_strings(cls, value: str | None) -> str | None:
        return clean(value)

    @field_validator("equipment")
    @classmethod
    def equipment_limit(cls, value: list[str]) -> list[str]:
        normalized = normalize_items(value)
        if len(normalized) > settings.max_drill_equipment_items:
            raise ValueError("too many equipment items")
        return normalized

    @field_validator("tags")
    @classmethod
    def tag_limit(cls, value: list[str]) -> list[str]:
        normalized = normalize_items(value)
        if len(normalized) > settings.max_drill_tags:
            raise ValueError("too many tags")
        return normalized


class DrillUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=settings.max_drill_title_characters)
    description: str | None = Field(default=None, max_length=settings.max_drill_description_characters)
    instructions: str | None = Field(default=None, min_length=1, max_length=settings.max_drill_instructions_characters)
    category: DrillCategory | None = None
    difficulty: DrillDifficulty | None = None
    equipment: list[str] | None = None
    estimated_duration_minutes: int | None = Field(default=None, gt=0)
    default_sets: int | None = Field(default=None, gt=0)
    default_repetitions: int | None = Field(default=None, gt=0)
    default_frequency: str | None = Field(default=None, max_length=200)
    tags: list[str] | None = None
    video_url: AnyHttpUrl | None = None

    @field_validator("title", "description", "instructions", "default_frequency", mode="before")
    @classmethod
    def clean_strings(cls, value: str | None) -> str | None:
        return clean(value)

    @field_validator("equipment")
    @classmethod
    def normalize_equipment(cls, value: list[str] | None) -> list[str] | None:
        return normalize_items(value) if value is not None else None

    @field_validator("tags")
    @classmethod
    def normalize_tags(cls, value: list[str] | None) -> list[str] | None:
        return normalize_items(value) if value is not None else None


class DrillResponse(BaseModel):
    id: UUID
    created_by_user_id: UUID
    title: str
    description: str | None
    instructions: str
    category: DrillCategory
    sport: str
    difficulty: DrillDifficulty
    equipment: list[str]
    estimated_duration_minutes: int | None
    default_sets: int | None
    default_repetitions: int | None
    default_frequency: str | None
    tags: list[str]
    video_url: str | None
    visibility: DrillVisibility
    status: DrillStatus
    created_at: datetime
    updated_at: datetime
    archived_at: datetime | None
    model_config = ConfigDict(from_attributes=True)


class DrillListResponse(BaseModel):
    items: list[DrillResponse]
    page: int
    page_size: int
    total: int
    total_pages: int
