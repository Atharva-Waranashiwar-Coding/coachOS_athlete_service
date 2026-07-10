import hmac
from dataclasses import dataclass

from fastapi import Header

from app.core.config import settings
from app.core.exceptions import ForbiddenError, UnauthorizedError

EVENT_ALLOWLIST = {
    "media-service": {
        "practice_session_created",
        "practice_session_completed",
        "practice_session_cancelled",
        "video_uploaded",
        "video_deleted",
    },
    "ai-review-service": {
        "ai_review_requested",
        "ai_review_generated",
        "ai_review_failed",
        "coach_review_edited",
        "coach_review_approved",
        "coach_review_rejected",
    },
    "drill-service": {"drill_assigned", "drill_updated", "drill_completed", "drill_cancelled"},
}


@dataclass(frozen=True)
class InternalServiceIdentity:
    name: str


def require_internal_service(
    x_service_name: str | None = Header(default=None), x_service_token: str | None = Header(default=None)
) -> InternalServiceIdentity:
    if not x_service_name or not x_service_token:
        raise UnauthorizedError("Internal service authentication is required.")
    expected = settings.internal_service_tokens.get(x_service_name)
    if not expected or not hmac.compare_digest(expected, x_service_token):
        raise UnauthorizedError("Invalid internal service credentials.")
    return InternalServiceIdentity(x_service_name)


def validate_internal_event(identity: InternalServiceIdentity, source_service: str, event_type: str) -> None:
    if source_service != identity.name:
        raise ForbiddenError("source_service does not match caller identity.")
    if event_type not in EVENT_ALLOWLIST.get(identity.name, set()):
        raise ForbiddenError("Event type is not allowed for this service.")
