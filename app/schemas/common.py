"""Shared API schemas."""

from typing import Any

from pydantic import BaseModel, Field


class ErrorDetail(BaseModel):
    """Standard API error body."""

    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class ErrorResponse(BaseModel):
    """Standard API error envelope."""

    error: ErrorDetail


class PaginatedResponse[T](BaseModel):
    """Generic paginated response envelope."""

    items: list[T]
    page: int
    page_size: int
    total: int
    total_pages: int
