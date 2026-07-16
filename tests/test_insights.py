"""Stage 10 deterministic insight calculation tests."""

from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core.exceptions import BadRequestError, UpstreamServiceError
from app.core.insight_rules import resolve_insight_period
from app.db.session import Base
from app.integrations.review_insights import (
    ApprovedReviewInsight,
    ApprovedReviewInsightBatch,
    ReviewInsightLabel,
)
from app.models.athlete import Athlete
from app.models.drill_assignment import DrillAssignment
from app.models.drill_assignment_activity import DrillAssignmentActivity
from app.models.enums import (
    AssignmentActorType,
    DrillActivityType,
    DrillAssignmentStatus,
    GoalCategory,
    GoalStatus,
)
from app.models.goal import AthleteGoal
from app.services.insights.drill_metrics_service import DrillMetricsService
from app.services.insights.goal_metrics_service import GoalMetricsService
from app.services.insights.progress_insight_service import ProgressInsightService
from app.services.insights.review_insight_service import (
    InsightLabelNormalizer,
    ReviewInsightAggregationService,
)


@pytest.fixture
def db() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        yield session
    Base.metadata.drop_all(engine)


def fixed_period():
    return resolve_insight_period(
        "30d",
        timezone="America/New_York",
        now=datetime(2026, 7, 16, 12, tzinfo=UTC),
    )


def test_time_ranges_are_half_open_and_validate_custom_bounds(monkeypatch):
    period = fixed_period()

    assert period.end > period.start
    assert period.previous_end == period.start
    assert period.end.astimezone(UTC).hour in {4, 5}

    custom = resolve_insight_period(
        "custom",
        start_date=date(2026, 7, 1),
        end_date=date(2026, 7, 10),
        compare=False,
        now=datetime(2026, 7, 16, tzinfo=UTC),
    )
    assert custom.previous_start is None
    assert (custom.end - custom.start).days == 10

    with pytest.raises(BadRequestError):
        resolve_insight_period("custom", start_date=date(2026, 7, 10), end_date=date(2026, 7, 1))
    monkeypatch.setattr("app.core.insight_rules.settings.insight_max_range_days", 5)
    with pytest.raises(BadRequestError):
        resolve_insight_period("custom", start_date=date(2026, 7, 1), end_date=date(2026, 7, 10))


def test_drill_metrics_exclude_cancelled_and_calculate_rates():
    period = fixed_period()
    athlete_id, coach_id = uuid4(), uuid4()
    completed = DrillAssignment(
        athlete_id=athlete_id,
        assigned_by_user_id=coach_id,
        title_snapshot="Completed",
        instructions_snapshot="Work",
        status=DrillAssignmentStatus.COMPLETED,
        assigned_at=period.start + timedelta(days=1),
        due_date=(period.start + timedelta(days=8)).date(),
        completion_percentage=100,
        completed_at=period.start + timedelta(days=7),
    )
    active = DrillAssignment(
        athlete_id=athlete_id,
        assigned_by_user_id=coach_id,
        title_snapshot="Active",
        instructions_snapshot="Work",
        status=DrillAssignmentStatus.IN_PROGRESS,
        assigned_at=period.start + timedelta(days=2),
        due_date=(period.start + timedelta(days=3)).date(),
        completion_percentage=40,
    )
    cancelled = DrillAssignment(
        athlete_id=athlete_id,
        assigned_by_user_id=coach_id,
        title_snapshot="Cancelled",
        instructions_snapshot="Work",
        status=DrillAssignmentStatus.CANCELLED,
        assigned_at=period.start + timedelta(days=2),
        cancelled_at=period.start + timedelta(days=4),
    )
    activities = [
        DrillAssignmentActivity(
            assignment_id=active.id,
            actor_user_id=coach_id,
            actor_type=AssignmentActorType.COACH,
            event_type=DrillActivityType.STARTED,
            occurred_at=period.start + timedelta(days=3),
        ),
        DrillAssignmentActivity(
            assignment_id=active.id,
            actor_user_id=coach_id,
            actor_type=AssignmentActorType.COACH,
            event_type=DrillActivityType.PROGRESS_UPDATED,
            progress_value=40,
            occurred_at=period.start + timedelta(days=4),
        ),
    ]

    metrics = DrillMetricsService().calculate([completed, active, cancelled], activities, period)

    assert metrics.current.assigned_count == 3
    assert metrics.current.completed_during_period == 1
    assert metrics.current.cancelled_count == 1
    assert metrics.current.completion_rate_sample_size == 2
    assert metrics.current.completion_rate == 50.0
    assert metrics.current.on_time_completion_rate == 100.0
    assert metrics.current.average_completion_days == 6.0
    assert metrics.current.average_progress_percentage == 40.0


def test_goal_metrics_and_recurring_review_normalization():
    period = fixed_period()
    athlete_id, coach_id = uuid4(), uuid4()
    goals = [
        AthleteGoal(
            athlete_id=athlete_id,
            title="Active",
            category=GoalCategory.HITTING,
            status=GoalStatus.ACTIVE,
            priority=1,
            target_date=period.end_local_date + timedelta(days=5),
            created_by_user_id=coach_id,
            created_at=period.start + timedelta(days=1),
            updated_at=period.start + timedelta(days=1),
        ),
        AthleteGoal(
            athlete_id=athlete_id,
            title="Completed",
            category=GoalCategory.FIELDING,
            status=GoalStatus.COMPLETED,
            priority=2,
            created_by_user_id=coach_id,
            created_at=period.start + timedelta(days=1),
            updated_at=period.start + timedelta(days=5),
            completed_at=period.start + timedelta(days=5),
        ),
    ]
    goal_metrics = GoalMetricsService().calculate(goals, period)
    assert goal_metrics.current.active_count == 1
    assert goal_metrics.current.completed_count == 1
    assert goal_metrics.current.completion_rate == 50.0
    assert goal_metrics.current.due_next_14_days == 1

    reviews = [
        ApprovedReviewInsight(
            review_id=uuid4(),
            athlete_id=athlete_id,
            review_type="hitting",
            approved_at=period.start + timedelta(days=day),
            visibility="coach_only",
            strengths=[ReviewInsightLabel(title="Balance", description="Stable")],
            improvement_areas=[
                ReviewInsightLabel(title="Swing timing", description="Work", priority="high"),
                ReviewInsightLabel(title="Timing consistency", description="Duplicate", priority="high"),
            ],
            practice_session_id=uuid4(),
            video_id=uuid4(),
        )
        for day in (2, 8)
    ]
    insight = ReviewInsightAggregationService().calculate(reviews, [], period)
    area = insight.recurring_improvement_areas[0]

    assert InsightLabelNormalizer().normalize(reviews[0].improvement_areas[0])[0] == "hitting.timing"
    assert area.distinct_review_count == 2
    assert area.high_priority_count == 2
    assert area.occurrence_count == 4


class EmptyReviews:
    def fetch(self, *args, **kwargs):
        return ApprovedReviewInsightBatch()


class FailedMedia:
    def fetch(self, *args, **kwargs):
        raise UpstreamServiceError()


def test_combined_insight_returns_local_data_when_media_is_unavailable(db: Session):
    athlete = Athlete(first_name="Maya", last_name="Torres")
    db.add(athlete)
    db.flush()
    db.add(
        DrillAssignment(
            athlete_id=athlete.id,
            assigned_by_user_id=uuid4(),
            title_snapshot="Reaction",
            instructions_snapshot="Complete controlled reps.",
            assigned_at=fixed_period().start + timedelta(days=2),
        )
    )
    db.commit()

    result = ProgressInsightService(db, reviews=EmptyReviews(), media=FailedMedia()).athlete(  # type: ignore[arg-type]
        athlete,
        uuid4(),
        fixed_period(),
    )

    assert result.drills is not None and result.drills.current.assigned_count == 1
    assert result.data_completeness.partial is True
    assert result.data_completeness.media_data_available is False
    assert result.data_completeness.warnings == ["media_data_unavailable"]
