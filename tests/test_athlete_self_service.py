"""Focused athlete self-service privacy and lifecycle tests."""

import os
from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret")

from app.core.exceptions import BadRequestError, UpstreamServiceError  # noqa: E402
from app.db.session import Base  # noqa: E402
from app.models.athlete import Athlete  # noqa: E402
from app.models.athlete_user_link import AthleteUserLink  # noqa: E402
from app.models.drill_assignment import DrillAssignment  # noqa: E402
from app.models.drill_assignment_activity import DrillAssignmentActivity  # noqa: E402
from app.models.enums import (  # noqa: E402
    AssignmentActorType,
    AthleteUserLinkStatus,
    DrillAssignmentStatus,
    EventCategory,
    GoalCategory,
    GoalStatus,
    TimelineVisibility,
    UserRole,
)
from app.models.goal import AthleteGoal  # noqa: E402
from app.models.timeline import TimelineEvent  # noqa: E402
from app.schemas.athlete_self import AthleteCompleteRequest, AthleteProgressRequest  # noqa: E402
from app.schemas.auth import CurrentAthlete  # noqa: E402
from app.services.athlete_self_service import AthleteSelfService  # noqa: E402
from app.services.progress_status_service import ProgressStatusService  # noqa: E402


@pytest.fixture
def db() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        yield session
    Base.metadata.drop_all(engine)


def seed(db: Session) -> tuple[CurrentAthlete, DrillAssignment]:
    athlete_id, auth_user_id, coach_id = uuid4(), uuid4(), uuid4()
    athlete = Athlete(
        id=athlete_id,
        first_name="Maya",
        last_name="Torres",
        preferred_name="MJ",
        injury_notes="Private injury plan",
        general_notes="Private coach note",
    )
    link = AthleteUserLink(
        athlete_id=athlete_id,
        auth_user_id=auth_user_id,
        invitation_email="maya@example.com",
        status=AthleteUserLinkStatus.ACTIVE,
        invited_by_user_id=coach_id,
        activated_at=datetime.now(UTC),
    )
    assignment = DrillAssignment(
        athlete_id=athlete_id,
        assigned_by_user_id=coach_id,
        title_snapshot="First-step reaction",
        description_snapshot="Improve initial movement.",
        instructions_snapshot="Complete three controlled rounds.",
        coach_notes="Private cue",
        due_date=date.today() + timedelta(days=2),
    )
    db.add_all([athlete, link, assignment])
    db.flush()
    db.add_all(
        [
            AthleteGoal(
                athlete_id=athlete_id,
                title="Improve first-step speed",
                category=GoalCategory.SPEED,
                status=GoalStatus.ACTIVE,
                created_by_user_id=coach_id,
            ),
            TimelineEvent(
                athlete_id=athlete_id,
                event_type="drill_assigned",
                event_category=EventCategory.DRILL,
                title="Drill assigned",
                source_service="athlete-service",
                source_entity_type="drill_assignment",
                source_entity_id=str(assignment.id),
                actor_user_id=coach_id,
                metadata_json={"assignment_id": str(assignment.id), "priority": 3, "private_note": "hidden"},
                visibility=TimelineVisibility.ATHLETE_VISIBLE,
            ),
            TimelineEvent(
                athlete_id=athlete_id,
                event_type="injury_note_updated",
                event_category=EventCategory.PROFILE,
                title="Private injury update",
                source_service="athlete-service",
                metadata_json={"changed": True},
                visibility=TimelineVisibility.COACH_ONLY,
            ),
        ]
    )
    db.commit()
    return (
        CurrentAthlete(
            auth_user_id=auth_user_id,
            athlete_id=athlete_id,
            email="maya@example.com",
            role=UserRole.ATHLETE,
            activated_at=link.activated_at,
        ),
        assignment,
    )


class UnavailableFeedbackClient:
    def get_athlete_feedback_summary(self, _: str):
        raise UpstreamServiceError()


def test_profile_and_timeline_use_athlete_safe_contracts(db: Session) -> None:
    current, _ = seed(db)
    service = AthleteSelfService(db)

    profile = service.profile(current).model_dump()
    timeline = service.timeline_list(
        current,
        page=1,
        page_size=20,
        event_type=None,
        event_category=None,
        source_service=None,
        start_date=None,
        end_date=None,
    )

    assert "injury_notes" not in profile and "general_notes" not in profile
    assert [item.title for item in timeline.items] == ["Drill assigned"]
    assert timeline.items[0].metadata == {"priority": 3}


def test_athlete_progress_records_actor_and_never_decreases(db: Session) -> None:
    current, assignment = seed(db)
    service = AthleteSelfService(db)

    updated = service.update_progress(
        current,
        assignment.id,
        AthleteProgressRequest(completion_percentage=40, athlete_note="Completed three rounds."),
    )
    activity = db.scalar(select(DrillAssignmentActivity).where(DrillAssignmentActivity.assignment_id == assignment.id))

    assert updated.status == DrillAssignmentStatus.IN_PROGRESS
    assert activity is not None and activity.actor_type == AssignmentActorType.ATHLETE
    assert activity.notes == "Completed three rounds."
    with pytest.raises(BadRequestError):
        service.update_progress(
            current,
            assignment.id,
            AthleteProgressRequest(completion_percentage=20),
        )


def test_completion_is_idempotent_and_timeline_omits_note(db: Session) -> None:
    current, assignment = seed(db)
    service = AthleteSelfService(db)
    payload = AthleteCompleteRequest(confirmation=True, athlete_note="Private completion detail.")

    first = service.complete_assignment(current, assignment.id, payload)
    second = service.complete_assignment(current, assignment.id, payload)
    completion_events = list(
        db.scalars(
            select(TimelineEvent).where(
                TimelineEvent.athlete_id == current.athlete_id,
                TimelineEvent.event_type == "drill_completed",
            )
        )
    )

    assert first.status == second.status == DrillAssignmentStatus.COMPLETED
    assert len(completion_events) == 1
    assert "Private completion detail." not in str(completion_events[0].metadata_json)


def test_dashboard_degrades_when_feedback_is_unavailable(db: Session) -> None:
    current, _ = seed(db)
    dashboard = AthleteSelfService(db, ai_reviews=UnavailableFeedbackClient()).dashboard(current, "token")  # type: ignore[arg-type]

    assert dashboard.partial_data is True
    assert dashboard.feedback_summary.available is False
    assert dashboard.drill_summary.active == 1
    assert dashboard.goal_summary.active == 1


def test_progress_status_rules_are_deterministic() -> None:
    assert (
        ProgressStatusService.calculate(
            active_assignments=0,
            overdue_assignments=0,
            completed_assignments=0,
            activated_at=None,
        ).code
        == "no_current_assignments"
    )
    assert (
        ProgressStatusService.calculate(
            active_assignments=1,
            overdue_assignments=1,
            completed_assignments=0,
            activated_at=None,
        ).code
        == "needs_attention"
    )
    assert (
        ProgressStatusService.calculate(
            active_assignments=1,
            overdue_assignments=0,
            completed_assignments=0,
            activated_at=None,
        ).code
        == "on_track"
    )
    assert (
        ProgressStatusService.calculate(
            active_assignments=0,
            overdue_assignments=0,
            completed_assignments=0,
            activated_at=datetime.now(UTC),
        ).code
        == "getting_started"
    )
