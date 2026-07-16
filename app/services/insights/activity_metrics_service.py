"""Combined authoritative activity counts across insight domains."""

from datetime import datetime

from app.core.insight_rules import InsightPeriod, as_utc
from app.integrations.media_service import AthleteMediaActivity
from app.models.drill_assignment import DrillAssignment
from app.models.drill_assignment_activity import DrillAssignmentActivity
from app.models.enums import DrillActivityType, TimelineVisibility
from app.models.goal import AthleteGoal
from app.models.timeline import TimelineEvent
from app.schemas.insights import ActivitySummary, CountComparison, DrillMetrics, GoalMetrics, ReviewInsights


class ActivityMetricsService:
    def calculate(
        self,
        period: InsightPeriod,
        assignments: list[DrillAssignment],
        activities: list[DrillAssignmentActivity],
        goals: list[AthleteGoal],
        timeline: list[TimelineEvent],
        drills: DrillMetrics,
        goal_metrics: GoalMetrics,
        reviews: ReviewInsights | None,
        media: AthleteMediaActivity | None,
    ) -> ActivitySummary:
        current_timeline = sum(
            item.visibility == TimelineVisibility.ATHLETE_VISIBLE
            and period.start <= as_utc(item.occurred_at) < period.end
            for item in timeline
        )
        previous_timeline = (
            sum(
                item.visibility == TimelineVisibility.ATHLETE_VISIBLE
                and period.previous_start <= as_utc(item.occurred_at) < period.previous_end
                for item in timeline
            )
            if period.previous_start and period.previous_end
            else None
        )
        latest = self._last_activity(assignments, activities, goals, reviews, media)
        return ActivitySummary(
            practice_sessions_created=self._compare(
                media.current.sessions_created if media else 0,
                media.previous.sessions_created if media and media.previous else None,
            ),
            practice_sessions_completed=self._compare(
                media.current.sessions_completed if media else 0,
                media.previous.sessions_completed if media and media.previous else None,
            ),
            videos_uploaded=self._compare(
                media.current.videos_uploaded if media else 0,
                media.previous.videos_uploaded if media and media.previous else None,
            ),
            approved_reviews=reviews.approved_review_count if reviews else self._compare(0, None),
            drills_assigned=self._compare(
                drills.current.assigned_count,
                drills.previous.assigned_count if drills.previous else None,
            ),
            drills_started=self._compare(
                drills.current.started_count,
                drills.previous.started_count if drills.previous else None,
            ),
            drills_completed=self._compare(
                drills.current.completed_during_period,
                drills.previous.completed_during_period if drills.previous else None,
            ),
            goals_created=self._compare(
                goal_metrics.current.created_during_period,
                goal_metrics.previous.created_during_period if goal_metrics.previous else None,
            ),
            goals_completed=self._compare(
                goal_metrics.current.completed_during_period,
                goal_metrics.previous.completed_during_period if goal_metrics.previous else None,
            ),
            athlete_visible_timeline_events=self._compare(current_timeline, previous_timeline),
            last_qualifying_activity=latest,
        )

    @staticmethod
    def _compare(current: int, previous: int | None) -> CountComparison:
        return CountComparison(
            current=current,
            previous=previous,
            absolute_change=current - previous if previous is not None else None,
        )

    @staticmethod
    def _last_activity(
        assignments: list[DrillAssignment],
        activities: list[DrillAssignmentActivity],
        goals: list[AthleteGoal],
        reviews: ReviewInsights | None,
        media: AthleteMediaActivity | None,
    ) -> datetime | None:
        values = [
            as_utc(item.occurred_at)
            for item in activities
            if item.event_type in {DrillActivityType.PROGRESS_UPDATED, DrillActivityType.COMPLETED}
        ]
        values.extend(as_utc(item.completed_at) for item in goals if item.completed_at)
        if reviews and reviews.latest_approved_at:
            values.append(reviews.latest_approved_at)
        if media and media.current.latest_session_at:
            values.append(media.current.latest_session_at)
        return max(values) if values else None
