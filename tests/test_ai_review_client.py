"""Unit tests for the approved AI review HTTP boundary."""

import os
from datetime import UTC, datetime
from uuid import uuid4

import httpx
import pytest

os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://postgres:postgres@localhost/coachos_test")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret")

from app.core.exceptions import NotFoundError, UpstreamServiceError  # noqa: E402
from app.integrations.ai_review_service import AIReviewServiceClient  # noqa: E402


def client_for(handler) -> AIReviewServiceClient:
    transport = httpx.MockTransport(handler)
    return AIReviewServiceClient(httpx.Client(transport=transport))


def approved_payload(review_id, athlete_id) -> dict:
    return {
        "review_id": str(review_id),
        "athlete_id": str(athlete_id),
        "status": "approved",
        "visibility": "coach_only",
        "approved_at": datetime.now(UTC).isoformat(),
        "recommended_drills": [
            {
                "name": "Command ladder",
                "description": "Work through each target.",
                "reason": "Approved rationale.",
                "frequency": "Twice weekly",
                "difficulty": "intermediate",
                "safety_note": None,
            }
        ],
    }


def test_approved_review_contract_is_parsed() -> None:
    review_id, athlete_id = uuid4(), uuid4()
    client = client_for(lambda _: httpx.Response(200, json=approved_payload(review_id, athlete_id)))

    review = client.get_approved_review(review_id, "coach-token")

    assert review.review_id == review_id
    assert review.athlete_id == athlete_id
    assert review.recommended_drills[0].name == "Command ladder"


@pytest.mark.parametrize("status_code", [401, 403, 404])
def test_inaccessible_review_is_hidden_as_not_found(status_code: int) -> None:
    client = client_for(lambda _: httpx.Response(status_code))

    with pytest.raises(NotFoundError):
        client.get_approved_review(uuid4(), "coach-token")


def test_upstream_failure_returns_service_unavailable() -> None:
    client = client_for(lambda _: httpx.Response(503))

    with pytest.raises(UpstreamServiceError):
        client.get_approved_review(uuid4(), "coach-token")


def test_invalid_or_unapproved_contract_is_rejected() -> None:
    client = client_for(
        lambda _: httpx.Response(
            200,
            json={
                "review_id": str(uuid4()),
                "athlete_id": str(uuid4()),
                "status": "generated",
                "visibility": "coach_only",
                "approved_at": datetime.now(UTC).isoformat(),
                "recommended_drills": [],
            },
        )
    )

    with pytest.raises(UpstreamServiceError):
        client.get_approved_review(uuid4(), "coach-token")


def test_transport_timeout_returns_service_unavailable() -> None:
    def timeout(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timed out", request=request)

    with pytest.raises(UpstreamServiceError):
        client_for(timeout).get_approved_review(uuid4(), "coach-token")
