"""Best-effort, coach-scoped assistant indexing for normalized timeline events."""
from uuid import UUID

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.athlete import CoachAthleteRelationship
from app.models.enums import RelationshipStatus


def index_timeline_event(db: Session, athlete_id: UUID, event: object) -> None:
    """Fan a trusted timeline event out to every active coach workspace.

    The timeline remains the durable producer boundary; indexing is deliberately
    non-blocking so an unavailable assistant never rejects source writes.
    """
    if not settings.assistant_internal_token:
        return
    coach_ids = db.scalars(
        select(CoachAthleteRelationship.coach_user_id).where(
            CoachAthleteRelationship.athlete_id == athlete_id,
            CoachAthleteRelationship.status == RelationshipStatus.ACTIVE,
        )
    ).all()
    content = "\n".join(part for part in [event.title, event.description or ""] if part).strip()
    if not content:
        return
    for coach_id in coach_ids:
        try:
            httpx.post(
                f"{settings.assistant_service_internal_url.rstrip('/')}/internal/index",
                json={
                    "entity_type": "timeline_event",
                    "entity_id": str(event.id),
                    "coach_id": str(coach_id),
                    "athlete_id": str(athlete_id),
                    "content": content,
                    "metadata": {"event_type": event.event_type, "source_service": event.source_service},
                },
                headers={"X-Service-Token": settings.assistant_internal_token},
                timeout=settings.upstream_timeout_seconds,
            ).raise_for_status()
        except httpx.HTTPError:
            # Timeline delivery is durable; a later reindex can repair this optional projection.
            continue
