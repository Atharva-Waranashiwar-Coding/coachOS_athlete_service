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
from app.main import app  # noqa: E402
from app.models.athlete import CoachAthleteRelationship  # noqa: E402
from app.models.enums import RelationshipRole, RelationshipStatus  # noqa: E402
from app.models.goal import AthleteGoal  # noqa: E402
from app.models.timeline import TimelineEvent  # noqa: E402

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
    with TestClient(app) as test_client:
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


def test_transaction_rolls_back_when_timeline_creation_fails(client: TestClient, db_session: Session, monkeypatch) -> None:
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
