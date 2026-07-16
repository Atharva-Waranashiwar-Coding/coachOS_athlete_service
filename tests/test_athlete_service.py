"""Integration tests for the Athlete Service.

These tests require a PostgreSQL database URL in TEST_DATABASE_URL. They are
skipped by default rather than substituting SQLite for PostgreSQL-specific
behavior such as JSONB and enum handling.
"""

import os
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

if not os.getenv("TEST_DATABASE_URL"):
    pytest.skip("TEST_DATABASE_URL is required for Athlete Service integration tests", allow_module_level=True)

os.environ.setdefault("APP_NAME", "coachos-athlete-service")
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("API_V1_PREFIX", "/api/v1")
os.environ.setdefault("DATABASE_URL", os.environ["TEST_DATABASE_URL"])
os.environ.setdefault("JWT_SECRET_KEY", "test-secret")
os.environ.setdefault("JWT_ALGORITHM", "HS256")
os.environ.setdefault("LOG_LEVEL", "INFO")
os.environ.setdefault("CORS_ORIGINS", "http://localhost:5173")
os.environ.setdefault("DEFAULT_PAGE_SIZE", "20")
os.environ.setdefault("MAX_PAGE_SIZE", "100")

from app.db.base import Base  # noqa: E402
from app.db.session import get_db  # noqa: E402
from app.integrations.ai_review_service import ApprovedRecommendation, ApprovedReview  # noqa: E402
from app.main import app  # noqa: E402
from app.models.athlete import CoachAthleteRelationship  # noqa: E402
from app.models.drill import Drill  # noqa: E402
from app.models.drill_assignment import DrillAssignment  # noqa: E402
from app.models.drill_assignment_activity import DrillAssignmentActivity  # noqa: E402
from app.models.enums import (  # noqa: E402
    DrillAssignmentStatus,
    DrillCategory,
    DrillDifficulty,
    DrillStatus,
    DrillVisibility,
    RelationshipRole,
    RelationshipStatus,
)
from app.models.goal import AthleteGoal  # noqa: E402
from app.models.timeline import TimelineEvent  # noqa: E402
from app.services.drill_assignment_service import DrillAssignmentService  # noqa: E402

engine = create_engine(os.environ["TEST_DATABASE_URL"], pool_pre_ping=True)
TestingSessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, expire_on_commit=False)


@pytest.fixture(autouse=True)
def reset_database() -> None:
    """Reset the PostgreSQL schema for each test."""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db_session() -> Session:
    """Provide a test database session."""
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(db_session: Session) -> TestClient:
    """Provide a TestClient with database dependency overrides."""

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def token(user_id=None, role: str = "coach", expired: bool = False) -> str:
    """Create a test Auth Service-compatible JWT."""
    subject = user_id or uuid4()
    exp = datetime.now(UTC) + (-timedelta(minutes=1) if expired else timedelta(minutes=30))
    return jwt.encode(
        {"sub": str(subject), "email": f"{subject}@example.com", "role": role, "exp": exp},
        os.environ["JWT_SECRET_KEY"],
        algorithm=os.environ["JWT_ALGORITHM"],
    )


def auth_headers(user_id=None, role: str = "coach", expired: bool = False) -> dict[str, str]:
    """Return authorization headers for a test user."""
    return {"Authorization": f"Bearer {token(user_id=user_id, role=role, expired=expired)}"}


def create_athlete(client: TestClient, coach_id, first_name: str = "Ava", last_name: str = "Stone") -> dict:
    """Create an athlete through the public API."""
    response = client.post(
        "/api/v1/athletes",
        json={
            "first_name": first_name,
            "last_name": last_name,
            "email": f"{first_name.lower()}.{last_name.lower()}@example.com",
            "primary_position": "pitcher",
            "secondary_positions": ["first_base"],
            "graduation_year": 2030,
            "injury_notes": "Private note",
        },
        headers=auth_headers(coach_id),
    )
    assert response.status_code == 201, response.text
    return response.json()


def create_drill(client: TestClient, coach_id, title: str = "Command ladder") -> dict:
    """Create a reusable drill through the public API."""
    response = client.post(
        "/api/v1/drills",
        json={
            "title": title,
            "description": "Build repeatable release-point command.",
            "instructions": "Complete five throws at each target.",
            "category": "pitching",
            "difficulty": "intermediate",
            "equipment": ["Baseball", "Targets", "baseball"],
            "estimated_duration_minutes": 20,
            "default_sets": 3,
            "default_repetitions": 5,
            "default_frequency": "Twice weekly",
            "tags": ["Command", "Accuracy", "command"],
        },
        headers=auth_headers(coach_id),
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_create_athlete_relationship_and_timeline(client: TestClient, db_session: Session) -> None:
    coach_id = uuid4()
    athlete = create_athlete(client, coach_id)

    relationship = db_session.execute(select(CoachAthleteRelationship)).scalar_one()
    event = db_session.execute(select(TimelineEvent)).scalar_one()

    assert relationship.coach_user_id == coach_id
    assert relationship.relationship_role == RelationshipRole.PRIMARY_COACH
    assert event.event_type == "athlete_created"
    assert event.athlete_id.hex == athlete["id"].replace("-", "")


def test_list_only_current_coach_athletes_and_excludes_notes(client: TestClient) -> None:
    coach_id = uuid4()
    other_coach_id = uuid4()
    create_athlete(client, coach_id, "Ava", "Stone")
    create_athlete(client, other_coach_id, "Mia", "Cole")

    response = client.get("/api/v1/athletes?search=ava&sort_by=first_name", headers=auth_headers(coach_id))

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["first_name"] == "Ava"
    assert "injury_notes" not in body["items"][0]
    assert "general_notes" not in body["items"][0]


def test_get_inaccessible_athlete_returns_404(client: TestClient) -> None:
    coach_id = uuid4()
    other_coach_id = uuid4()
    athlete = create_athlete(client, coach_id)

    response = client.get(f"/api/v1/athletes/{athlete['id']}", headers=auth_headers(other_coach_id))

    assert response.status_code == 404


def test_non_coach_and_invalid_tokens_are_rejected(client: TestClient) -> None:
    athlete_response = client.post(
        "/api/v1/athletes",
        json={"first_name": "Ava", "last_name": "Stone"},
        headers=auth_headers(role="athlete"),
    )
    expired_response = client.get("/api/v1/athletes", headers=auth_headers(expired=True))

    assert athlete_response.status_code == 403
    assert expired_response.status_code == 401


def test_update_requires_primary_coach(client: TestClient, db_session: Session) -> None:
    primary_coach_id = uuid4()
    assistant_coach_id = uuid4()
    athlete = create_athlete(client, primary_coach_id)
    db_session.add(
        CoachAthleteRelationship(
            coach_user_id=assistant_coach_id,
            athlete_id=UUID(athlete["id"]),
            relationship_role=RelationshipRole.ASSISTANT_COACH,
            status=RelationshipStatus.ACTIVE,
        )
    )
    db_session.commit()

    denied = client.patch(
        f"/api/v1/athletes/{athlete['id']}",
        json={"first_name": "Updated"},
        headers=auth_headers(assistant_coach_id),
    )
    allowed = client.patch(
        f"/api/v1/athletes/{athlete['id']}",
        json={"first_name": "Updated", "injury_notes": "New private note"},
        headers=auth_headers(primary_coach_id),
    )

    assert denied.status_code == 403
    assert allowed.status_code == 200
    assert allowed.json()["first_name"] == "Updated"


def test_archive_and_restore_athlete(client: TestClient) -> None:
    coach_id = uuid4()
    athlete = create_athlete(client, coach_id)

    archived = client.delete(f"/api/v1/athletes/{athlete['id']}", headers=auth_headers(coach_id))
    restored = client.post(f"/api/v1/athletes/{athlete['id']}/restore", headers=auth_headers(coach_id))

    assert archived.status_code == 204
    assert restored.status_code == 200
    assert restored.json()["status"] == "active"
    assert restored.json()["archived_at"] is None


def test_goal_create_complete_and_cancel(client: TestClient, db_session: Session) -> None:
    coach_id = uuid4()
    athlete = create_athlete(client, coach_id)

    created = client.post(
        f"/api/v1/athletes/{athlete['id']}/goals",
        json={"title": "Improve command", "category": "pitching", "priority": 1},
        headers=auth_headers(coach_id),
    )
    goal_id = created.json()["id"]
    completed = client.patch(
        f"/api/v1/athletes/{athlete['id']}/goals/{goal_id}",
        json={"status": "completed"},
        headers=auth_headers(coach_id),
    )
    cancelled = client.delete(f"/api/v1/athletes/{athlete['id']}/goals/{goal_id}", headers=auth_headers(coach_id))
    goal = db_session.get(AthleteGoal, UUID(goal_id))

    assert created.status_code == 201
    assert completed.status_code == 200
    assert completed.json()["completed_at"] is not None
    assert cancelled.status_code == 204
    assert goal.status.value == "cancelled"


def test_timeline_ordering_and_filtering(client: TestClient) -> None:
    coach_id = uuid4()
    athlete = create_athlete(client, coach_id)
    client.patch(f"/api/v1/athletes/{athlete['id']}", json={"first_name": "Updated"}, headers=auth_headers(coach_id))

    response = client.get(
        f"/api/v1/athletes/{athlete['id']}/timeline?event_type=athlete_updated",
        headers=auth_headers(coach_id),
    )

    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert response.json()["items"][0]["event_type"] == "athlete_updated"


def test_validation_failures(client: TestClient) -> None:
    response = client.post(
        "/api/v1/athletes",
        json={"first_name": " ", "last_name": "Stone", "height_inches": -1},
        headers=auth_headers(uuid4()),
    )

    assert response.status_code == 422


def test_transaction_rolls_back_when_timeline_creation_fails(
    client: TestClient, db_session: Session, monkeypatch
) -> None:
    from app.services.timeline_service import TimelineService

    def fail_timeline(*args, **kwargs):
        raise RuntimeError("timeline failed")

    monkeypatch.setattr(TimelineService, "create_event", fail_timeline)

    response = client.post(
        "/api/v1/athletes",
        json={"first_name": "Ava", "last_name": "Stone"},
        headers=auth_headers(uuid4()),
    )

    assert response.status_code == 500
    assert db_session.execute(select(CoachAthleteRelationship)).scalars().all() == []


def test_drill_library_ownership_filters_archive_and_restore(client: TestClient, db_session: Session) -> None:
    coach_id, other_coach_id = uuid4(), uuid4()
    drill = create_drill(client, coach_id)
    create_drill(client, other_coach_id, "Private hitting drill")

    listed = client.get(
        "/api/v1/drills?search=command&category=pitching&difficulty=intermediate&tag=command",
        headers=auth_headers(coach_id),
    )
    inaccessible = client.get(f"/api/v1/drills/{drill['id']}", headers=auth_headers(other_coach_id))
    archived = client.delete(f"/api/v1/drills/{drill['id']}", headers=auth_headers(coach_id))
    active_list = client.get("/api/v1/drills", headers=auth_headers(coach_id))
    archived_list = client.get("/api/v1/drills?status=archived", headers=auth_headers(coach_id))
    restored = client.post(f"/api/v1/drills/{drill['id']}/restore", headers=auth_headers(coach_id))

    assert listed.status_code == 200
    assert listed.json()["total"] == 1
    assert listed.json()["items"][0]["equipment"] == ["baseball", "targets"]
    assert inaccessible.status_code == 404
    assert archived.status_code == 204
    assert active_list.json()["total"] == 0
    assert archived_list.json()["total"] == 1
    assert restored.status_code == 200
    assert restored.json()["status"] == "active"
    assert db_session.get(Drill, UUID(drill["id"])) is not None


def test_system_drill_is_readable_and_read_only(client: TestClient, db_session: Session) -> None:
    system_drill = Drill(
        created_by_user_id=uuid4(),
        title="System footwork",
        instructions="Move through the ladder under control.",
        category=DrillCategory.FOOTWORK,
        difficulty=DrillDifficulty.BEGINNER,
        visibility=DrillVisibility.SYSTEM,
        status=DrillStatus.ACTIVE,
        equipment=["ladder"],
        tags=["footwork"],
    )
    db_session.add(system_drill)
    db_session.commit()

    fetched = client.get(f"/api/v1/drills/{system_drill.id}", headers=auth_headers(uuid4()))
    updated = client.patch(
        f"/api/v1/drills/{system_drill.id}",
        json={"title": "Changed"},
        headers=auth_headers(uuid4()),
    )

    assert fetched.status_code == 200
    assert updated.status_code == 404


def test_library_assignment_snapshots_content_and_survives_drill_archive(
    client: TestClient, db_session: Session
) -> None:
    coach_id = uuid4()
    athlete = create_athlete(client, coach_id)
    drill = create_drill(client, coach_id)

    created = client.post(
        f"/api/v1/athletes/{athlete['id']}/drill-assignments",
        json={
            "mode": "library",
            "drill_id": drill["id"],
            "priority": 2,
            "target_sets": 4,
            "due_date": "2030-04-15",
            "coach_notes": "Private mechanical cue.",
        },
        headers=auth_headers(coach_id),
    )
    assignment_id = created.json()["id"]
    client.patch(
        f"/api/v1/drills/{drill['id']}",
        json={"title": "Updated library title", "instructions": "Updated instructions."},
        headers=auth_headers(coach_id),
    )
    client.delete(f"/api/v1/drills/{drill['id']}", headers=auth_headers(coach_id))
    detail = client.get(
        f"/api/v1/athletes/{athlete['id']}/drill-assignments/{assignment_id}",
        headers=auth_headers(coach_id),
    )
    rejected = client.post(
        f"/api/v1/athletes/{athlete['id']}/drill-assignments",
        json={"mode": "library", "drill_id": drill["id"]},
        headers=auth_headers(coach_id),
    )

    event = db_session.scalar(select(TimelineEvent).where(TimelineEvent.event_type == "drill_assigned"))
    activity = db_session.scalar(select(DrillAssignmentActivity))
    assert created.status_code == 201
    assert detail.json()["title_snapshot"] == "Command ladder"
    assert detail.json()["instructions_snapshot"] == "Complete five throws at each target."
    assert rejected.status_code == 404
    assert activity is not None and activity.event_type.value == "assigned"
    assert event is not None
    assert "coach_notes" not in event.metadata_json
    assert "Private mechanical cue" not in str(event.metadata_json)


def test_assignment_requires_primary_coach_and_accessible_drill(client: TestClient, db_session: Session) -> None:
    primary_id, assistant_id, other_id = uuid4(), uuid4(), uuid4()
    athlete = create_athlete(client, primary_id)
    private_drill = create_drill(client, other_id)
    db_session.add(
        CoachAthleteRelationship(
            coach_user_id=assistant_id,
            athlete_id=UUID(athlete["id"]),
            relationship_role=RelationshipRole.ASSISTANT_COACH,
            status=RelationshipStatus.ACTIVE,
        )
    )
    db_session.commit()

    assistant = client.post(
        f"/api/v1/athletes/{athlete['id']}/drill-assignments",
        json={"mode": "custom", "title": "Custom", "instructions": "Do the work."},
        headers=auth_headers(assistant_id),
    )
    inaccessible_drill = client.post(
        f"/api/v1/athletes/{athlete['id']}/drill-assignments",
        json={"mode": "library", "drill_id": private_drill["id"]},
        headers=auth_headers(primary_id),
    )

    assert assistant.status_code == 403
    assert inaccessible_drill.status_code == 404


def test_ad_hoc_assignment_lifecycle_is_idempotent_and_terminal(client: TestClient) -> None:
    coach_id = uuid4()
    athlete = create_athlete(client, coach_id)
    created = client.post(
        f"/api/v1/athletes/{athlete['id']}/drill-assignments",
        json={
            "mode": "custom",
            "title": "<b>Recovery circuit</b>",
            "description": "Post-session reset.",
            "instructions": "Complete controlled mobility work.",
            "priority": 3,
        },
        headers=auth_headers(coach_id),
    )
    assignment_id = created.json()["id"]
    started = client.post(
        f"/api/v1/athletes/{athlete['id']}/drill-assignments/{assignment_id}/start",
        headers=auth_headers(coach_id),
    )
    started_again = client.post(
        f"/api/v1/athletes/{athlete['id']}/drill-assignments/{assignment_id}/start",
        headers=auth_headers(coach_id),
    )
    completed = client.post(
        f"/api/v1/athletes/{athlete['id']}/drill-assignments/{assignment_id}/complete",
        json={"completion_notes": "Private completion note.", "actual_duration_minutes": 18},
        headers=auth_headers(coach_id),
    )
    completed_again = client.post(
        f"/api/v1/athletes/{athlete['id']}/drill-assignments/{assignment_id}/complete",
        json={},
        headers=auth_headers(coach_id),
    )
    cancelled = client.post(
        f"/api/v1/athletes/{athlete['id']}/drill-assignments/{assignment_id}/cancel",
        json={"reason": "Should remain private."},
        headers=auth_headers(coach_id),
    )

    assert created.status_code == 201
    assert created.json()["title_snapshot"] == "Recovery circuit"
    assert started.json()["status"] == DrillAssignmentStatus.IN_PROGRESS.value
    assert started_again.status_code == 200
    assert completed.json()["status"] == DrillAssignmentStatus.COMPLETED.value
    assert completed.json()["completion_percentage"] == 100
    assert completed_again.status_code == 200
    assert cancelled.status_code == 400


class FakeAIReviewClient:
    def __init__(self, review: ApprovedReview) -> None:
        self.review = review

    def get_approved_review(self, review_id: UUID, bearer_token: str) -> ApprovedReview:
        assert review_id == self.review.review_id
        assert bearer_token
        return self.review


def test_review_assignment_uses_trusted_approved_content_and_can_save_drill(
    client: TestClient, db_session: Session
) -> None:
    from app.api.v1.endpoints.drill_assignments import get_service

    coach_id, review_id = uuid4(), uuid4()
    athlete = create_athlete(client, coach_id)
    approved = ApprovedReview(
        review_id=review_id,
        athlete_id=UUID(athlete["id"]),
        status="approved",
        visibility="coach_only",
        approved_at=datetime.now(UTC),
        recommended_drills=[
            ApprovedRecommendation(
                name="Trusted recommendation",
                description="Approved description.",
                reason="Private AI rationale.",
                frequency="Three times weekly",
                difficulty=DrillDifficulty.ADVANCED,
                safety_note="Stop if pain develops.",
            )
        ],
    )
    app.dependency_overrides[get_service] = lambda: DrillAssignmentService(db_session, FakeAIReviewClient(approved))
    try:
        response = client.post(
            f"/api/v1/athletes/{athlete['id']}/drill-assignments",
            json={
                "mode": "review",
                "source_review_id": str(review_id),
                "source_recommendation_index": 0,
                "save_to_library": True,
                "title": "Forged frontend content",
                "reason": "Forged reason",
            },
            headers=auth_headers(coach_id),
        )
    finally:
        app.dependency_overrides.pop(get_service, None)

    body = response.json()
    timeline = db_session.scalar(select(TimelineEvent).where(TimelineEvent.event_type == "drill_assigned"))
    assert response.status_code == 201
    assert body["title_snapshot"] == "Trusted recommendation"
    assert body["frequency"] == "Three times weekly"
    assert body["drill_id"] is not None
    assert "Stop if pain develops." in body["instructions_snapshot"]
    assert db_session.get(Drill, UUID(body["drill_id"])) is not None
    assert timeline is not None
    assert "Private AI rationale." not in str(timeline.metadata_json)


def test_review_assignment_can_map_to_existing_library_drill(client: TestClient, db_session: Session) -> None:
    from app.api.v1.endpoints.drill_assignments import get_service

    coach_id, review_id = uuid4(), uuid4()
    athlete = create_athlete(client, coach_id)
    drill = create_drill(client, coach_id, "Mapped library drill")
    approved = ApprovedReview(
        review_id=review_id,
        athlete_id=UUID(athlete["id"]),
        status="approved",
        visibility="coach_only",
        approved_at=datetime.now(UTC),
        recommended_drills=[
            ApprovedRecommendation(
                name="Approved recommendation snapshot",
                description="Approved description.",
                reason="Coach-only rationale.",
                difficulty=DrillDifficulty.INTERMEDIATE,
            )
        ],
    )
    app.dependency_overrides[get_service] = lambda: DrillAssignmentService(db_session, FakeAIReviewClient(approved))
    try:
        response = client.post(
            f"/api/v1/athletes/{athlete['id']}/drill-assignments",
            json={
                "mode": "review",
                "source_review_id": str(review_id),
                "source_recommendation_index": 0,
                "mapped_drill_id": drill["id"],
            },
            headers=auth_headers(coach_id),
        )
    finally:
        app.dependency_overrides.pop(get_service, None)

    assert response.status_code == 201
    assert response.json()["drill_id"] == drill["id"]
    assert response.json()["title_snapshot"] == "Approved recommendation snapshot"


def test_review_assignment_rejects_mismatch_and_missing_recommendation(client: TestClient, db_session: Session) -> None:
    from app.api.v1.endpoints.drill_assignments import get_service

    coach_id, review_id = uuid4(), uuid4()
    athlete = create_athlete(client, coach_id)
    approved = ApprovedReview(
        review_id=review_id,
        athlete_id=uuid4(),
        status="approved",
        visibility="coach_only",
        approved_at=datetime.now(UTC),
        recommended_drills=[],
    )
    app.dependency_overrides[get_service] = lambda: DrillAssignmentService(db_session, FakeAIReviewClient(approved))
    try:
        mismatch = client.post(
            f"/api/v1/athletes/{athlete['id']}/drill-assignments",
            json={
                "mode": "review",
                "source_review_id": str(review_id),
                "source_recommendation_index": 0,
            },
            headers=auth_headers(coach_id),
        )
        approved.athlete_id = UUID(athlete["id"])
        missing = client.post(
            f"/api/v1/athletes/{athlete['id']}/drill-assignments",
            json={
                "mode": "review",
                "source_review_id": str(review_id),
                "source_recommendation_index": 0,
            },
            headers=auth_headers(coach_id),
        )
    finally:
        app.dependency_overrides.pop(get_service, None)

    assert mismatch.status_code == 404
    assert missing.status_code == 404


def test_assignment_transaction_rolls_back_when_timeline_fails(
    client: TestClient, db_session: Session, monkeypatch
) -> None:
    from app.services.timeline_service import TimelineService

    coach_id = uuid4()
    athlete = create_athlete(client, coach_id)

    def fail_timeline(*args, **kwargs):
        raise RuntimeError("timeline failed")

    monkeypatch.setattr(TimelineService, "create_event", fail_timeline)
    response = client.post(
        f"/api/v1/athletes/{athlete['id']}/drill-assignments",
        json={"mode": "custom", "title": "Rollback drill", "instructions": "Should not persist."},
        headers=auth_headers(coach_id),
    )

    assert response.status_code == 500
    assert db_session.scalars(select(DrillAssignment)).all() == []
    assert db_session.scalars(select(DrillAssignmentActivity)).all() == []
