from uuid import UUID

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies.internal_auth import InternalServiceIdentity, require_internal_service, validate_internal_event
from app.schemas.timeline import TimelineEventResponse, TimelineIngestionRequest
from app.services.timeline_service import TimelineService
from app.integrations.assistant_index import index_timeline_event

router = APIRouter(prefix="/athletes/{athlete_id}/timeline-events", tags=["internal-timeline"])


@router.post("", response_model=TimelineEventResponse, status_code=201)
def ingest_timeline_event(
    athlete_id: UUID,
    payload: TimelineIngestionRequest,
    response: Response,
    identity: InternalServiceIdentity = Depends(require_internal_service),
    db: Session = Depends(get_db),
) -> TimelineEventResponse:
    if athlete_id != payload.athlete_id:
        from app.core.exceptions import BadRequestError

        raise BadRequestError("Path athlete_id must match request body.")
    validate_internal_event(identity, payload.source_service, payload.event_type)
    event, created = TimelineService(db).ingest(payload)
    if created:
        index_timeline_event(db, athlete_id, event)
    response.status_code = status.HTTP_201_CREATED if created else status.HTTP_200_OK
    return event
