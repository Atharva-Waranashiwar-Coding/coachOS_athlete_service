"""Bounded Media Service activity insight client."""

from datetime import datetime
from uuid import UUID

import httpx
from pydantic import BaseModel, Field, ValidationError

from app.core.config import settings
from app.core.exceptions import UpstreamServiceError


class MediaActivityPeriod(BaseModel):
    sessions_created: int = 0
    sessions_completed: int = 0
    videos_uploaded: int = 0
    latest_session_at: datetime | None = None


class AthleteMediaActivity(BaseModel):
    athlete_id: UUID
    current: MediaActivityPeriod
    previous: MediaActivityPeriod | None = None


class MediaActivityBatch(BaseModel):
    items: list[AthleteMediaActivity] = Field(default_factory=list)


class MediaInsightClient:
    def __init__(self, client: httpx.Client | None = None) -> None:
        self.client = client or httpx.Client(timeout=settings.insight_upstream_timeout_seconds)

    def fetch(
        self,
        athlete_ids: list[UUID],
        coach_user_id: UUID,
        start: datetime,
        end: datetime,
        previous_start: datetime | None,
        previous_end: datetime | None,
    ) -> MediaActivityBatch:
        items: list[AthleteMediaActivity] = []
        for offset in range(0, len(athlete_ids), settings.insight_max_batch_athletes):
            batch = athlete_ids[offset : offset + settings.insight_max_batch_athletes]
            try:
                response = self.client.post(
                    f"{settings.media_service_internal_url.rstrip('/')}/api/v1/insights/athletes/activity-summary",
                    headers={
                        "X-Service-Name": settings.internal_service_name,
                        "X-Service-Token": settings.internal_service_token,
                    },
                    json={
                        "athlete_ids": [str(item) for item in batch],
                        "coach_user_id": str(coach_user_id),
                        "start_date": start.isoformat(),
                        "end_date": end.isoformat(),
                        "comparison_start": previous_start.isoformat() if previous_start else None,
                        "comparison_end": previous_end.isoformat() if previous_end else None,
                    },
                )
            except httpx.HTTPError as exc:
                raise UpstreamServiceError("Media insight data is unavailable.") from exc
            if response.status_code != 200:
                raise UpstreamServiceError("Media insight data is unavailable.")
            try:
                items.extend(MediaActivityBatch.model_validate(response.json()).items)
            except ValidationError as exc:
                raise UpstreamServiceError("Media Service returned an invalid insight contract.") from exc
        return MediaActivityBatch(items=items)
