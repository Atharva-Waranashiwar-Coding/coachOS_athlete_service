"""Authenticated client for immutable approved AI review snapshots."""

from datetime import datetime
from typing import Literal
from uuid import UUID

import httpx
from pydantic import BaseModel, Field, ValidationError

from app.core.config import settings
from app.core.exceptions import NotFoundError, UpstreamServiceError
from app.models.enums import DrillDifficulty


class ApprovedRecommendation(BaseModel):
    name: str
    description: str
    reason: str
    frequency: str | None = None
    difficulty: DrillDifficulty
    safety_note: str | None = None


class ApprovedReview(BaseModel):
    review_id: UUID
    athlete_id: UUID
    status: Literal["approved"]
    visibility: str
    recommended_drills: list[ApprovedRecommendation] = Field(default_factory=list)
    approved_at: datetime


class AthleteFeedbackSummary(BaseModel):
    athlete_visible_approved_count: int
    latest_approved_at: datetime | None = None


class AIReviewServiceClient:
    def __init__(self, client: httpx.Client | None = None) -> None:
        self.client = client or httpx.Client(timeout=settings.upstream_timeout_seconds)

    def get_approved_review(self, review_id: UUID, bearer_token: str) -> ApprovedReview:
        try:
            response = self.client.get(
                f"{settings.ai_review_service_url.rstrip('/')}/api/v1/reviews/{review_id}/approved",
                headers={"Authorization": f"Bearer {bearer_token}"},
            )
        except httpx.HTTPError as exc:
            raise UpstreamServiceError("AI Review Service is unavailable.") from exc
        if response.status_code in {401, 403, 404}:
            raise NotFoundError("Approved review not found.")
        if response.status_code >= 500:
            raise UpstreamServiceError("AI Review Service is unavailable.")
        if response.status_code != 200:
            raise NotFoundError("Approved review not found.")
        try:
            return ApprovedReview.model_validate(response.json())
        except ValidationError as exc:
            raise UpstreamServiceError("AI Review Service returned an invalid approved-review contract.") from exc

    def get_athlete_feedback_summary(self, bearer_token: str) -> AthleteFeedbackSummary:
        """Return a minimal summary from the athlete-safe review collection."""
        try:
            response = self.client.get(
                f"{settings.ai_review_service_url.rstrip('/')}/api/v1/athlete/reviews",
                params={"page": 1, "page_size": 1},
                headers={"Authorization": f"Bearer {bearer_token}"},
            )
        except httpx.HTTPError as exc:
            raise UpstreamServiceError("AI Review Service is unavailable.") from exc
        if response.status_code >= 400:
            raise UpstreamServiceError("AI Review Service could not provide athlete feedback.")
        try:
            payload = response.json()
            items = payload.get("items", [])
            return AthleteFeedbackSummary(
                athlete_visible_approved_count=int(payload["total"]),
                latest_approved_at=items[0]["approved_at"] if items else None,
            )
        except (KeyError, TypeError, ValueError, ValidationError) as exc:
            raise UpstreamServiceError("AI Review Service returned an invalid athlete-feedback contract.") from exc
