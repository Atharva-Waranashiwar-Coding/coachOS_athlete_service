"""Bounded AI Review Service approved insight client."""

from datetime import datetime
from typing import Literal
from uuid import UUID

import httpx
from pydantic import BaseModel, Field, ValidationError

from app.core.config import settings
from app.core.exceptions import UpstreamServiceError


class ReviewInsightLabel(BaseModel):
    title: str
    description: str
    priority: Literal["low", "medium", "high"] | None = None
    taxonomy_code: str | None = None


class ApprovedReviewInsight(BaseModel):
    review_id: UUID
    athlete_id: UUID
    review_type: str
    approved_at: datetime
    visibility: str
    strengths: list[ReviewInsightLabel] = Field(default_factory=list)
    improvement_areas: list[ReviewInsightLabel] = Field(default_factory=list)
    recommended_drills: list[dict] = Field(default_factory=list)
    practice_session_id: UUID
    video_id: UUID


class ApprovedReviewInsightBatch(BaseModel):
    items: list[ApprovedReviewInsight] = Field(default_factory=list)


class ReviewInsightClient:
    def __init__(self, client: httpx.Client | None = None) -> None:
        self.client = client or httpx.Client(timeout=settings.insight_upstream_timeout_seconds)

    def fetch(
        self,
        athlete_ids: list[UUID],
        start: datetime,
        end: datetime,
        previous_start: datetime | None,
        previous_end: datetime | None,
    ) -> ApprovedReviewInsightBatch:
        items: list[ApprovedReviewInsight] = []
        for offset in range(0, len(athlete_ids), settings.insight_max_batch_athletes):
            batch = athlete_ids[offset : offset + settings.insight_max_batch_athletes]
            try:
                response = self.client.post(
                    f"{settings.ai_review_service_internal_url.rstrip('/')}"
                    "/api/v1/insights/athletes/approved-review-summary",
                    headers={
                        "X-Service-Name": settings.internal_service_name,
                        "X-Service-Token": settings.internal_service_token,
                    },
                    json={
                        "athlete_ids": [str(item) for item in batch],
                        "start_date": start.isoformat(),
                        "end_date": end.isoformat(),
                        "comparison_start": previous_start.isoformat() if previous_start else None,
                        "comparison_end": previous_end.isoformat() if previous_end else None,
                    },
                )
            except httpx.HTTPError as exc:
                raise UpstreamServiceError("Approved review insight data is unavailable.") from exc
            if response.status_code != 200:
                raise UpstreamServiceError("Approved review insight data is unavailable.")
            try:
                items.extend(ApprovedReviewInsightBatch.model_validate(response.json()).items)
            except ValidationError as exc:
                raise UpstreamServiceError("AI Review Service returned an invalid insight contract.") from exc
        return ApprovedReviewInsightBatch(items=items)
