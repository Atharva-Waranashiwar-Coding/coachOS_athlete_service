"""Coach-facing progress insight orchestration with partial upstream data."""

from collections import Counter
from datetime import UTC, datetime
from math import ceil
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.insight_rules import InsightPeriod, as_utc
from app.integrations.media_service import MediaInsightClient
from app.integrations.review_insights import ApprovedReviewInsight, ReviewInsightClient
from app.models.athlete import Athlete
from app.models.enums import AthleteStatus
from app.repositories.insight_queries import InsightQueries
from app.schemas.insights import (
    AthleteInsightSummary,
    AthleteProgressInsights,
    CoachAttentionItem,
    CoachAttentionPage,
    CoachInsightsResponse,
    DataCompleteness,
    InsightPeriodResponse,
    RecentProgressItem,
)
from app.services.insights.activity_metrics_service import ActivityMetricsService
from app.services.insights.attention_flag_service import AttentionFlagService
from app.services.insights.drill_metrics_service import DrillMetricsService
from app.services.insights.goal_metrics_service import GoalMetricsService
from app.services.insights.review_insight_service import ReviewInsightAggregationService

ALL_SECTIONS = {"activity", "drills", "goals", "reviews", "attention"}


class ProgressInsightService:
    def __init__(
        self,
        db: Session,
        reviews: ReviewInsightClient | None = None,
        media: MediaInsightClient | None = None,
    ) -> None:
        self.queries = InsightQueries(db)
        self.review_client = reviews or ReviewInsightClient()
        self.media_client = media or MediaInsightClient()

    def athlete(
        self,
        athlete: Athlete,
        coach_user_id: UUID,
        period: InsightPeriod,
        sections: set[str] | None = None,
    ) -> AthleteProgressInsights:
        return self._build([athlete], coach_user_id, period, sections)[0]

    def coach(
        self,
        coach_user_id: UUID,
        period: InsightPeriod,
        status: AthleteStatus | None = None,
        page: int = 1,
        page_size: int = 5,
    ) -> CoachInsightsResponse:
        athletes = self.queries.athletes_for_coach(coach_user_id, status)
        insights = self._build(athletes, coach_user_id, period, None) if athletes else []
        attention = [self._attention_item(item) for item in insights if item.attention_flags]
        recurring = Counter(
            area.key for item in insights if item.reviews for area in item.reviews.recurring_improvement_areas
        )
        top = []
        for key, _ in recurring.most_common(5):
            candidates = [
                area
                for item in insights
                if item.reviews
                for area in item.reviews.recurring_improvement_areas
                if area.key == key
            ]
            if candidates:
                top.append(max(candidates, key=lambda item: item.distinct_review_count))
        recent = sorted(
            [event for item in insights for event in item.recent_milestones],
            key=lambda item: item.occurred_at,
            reverse=True,
        )[:10]
        completeness = self._combined_completeness(insights)
        attention_total = len(attention)
        attention_start = (page - 1) * page_size
        return CoachInsightsResponse(
            period=self._period(period),
            active_athlete_count=sum(item.athlete.status == AthleteStatus.ACTIVE for item in insights),
            athletes_with_attention_flags=len(attention),
            total_overdue_assignments=sum(item.drills.current.overdue_count for item in insights if item.drills),
            total_active_assignments=sum(item.drills.current.active_count for item in insights if item.drills),
            completed_drills_during_period=sum(
                item.drills.current.completed_during_period for item in insights if item.drills
            ),
            approved_reviews_during_period=(
                sum(item.reviews.approved_review_count.current for item in insights if item.reviews)
                if completeness.review_data_available
                else None
            ),
            completed_practice_sessions_during_period=(
                sum(item.activity.practice_sessions_completed.current for item in insights if item.activity)
                if completeness.media_data_available
                else None
            ),
            top_recurring_improvement_areas=top,
            recent_progress_items=recent,
            attention_items=attention[attention_start : attention_start + page_size],
            attention_page=page,
            attention_page_size=page_size,
            attention_total=attention_total,
            attention_total_pages=ceil(attention_total / page_size) if attention_total else 0,
            data_completeness=completeness,
            generated_at=datetime.now(UTC),
        )

    def attention_page(
        self,
        coach_user_id: UUID,
        period: InsightPeriod,
        *,
        severity: str | None,
        flag_code: str | None,
        primary_position: str | None,
        search: str | None,
        sort_by: str,
        page: int,
        page_size: int,
    ) -> CoachAttentionPage:
        insights = self._build(self.queries.athletes_for_coach(coach_user_id), coach_user_id, period, None)
        items = [self._attention_item(item) for item in insights if item.attention_flags]
        if severity:
            items = [item for item in items if any(flag.severity == severity for flag in item.attention_flags)]
        if flag_code:
            items = [item for item in items if any(flag.code == flag_code for flag in item.attention_flags)]
        if primary_position:
            items = [
                item
                for item in items
                if item.athlete.primary_position and item.athlete.primary_position.value == primary_position
            ]
        if search:
            needle = search.lower()
            items = [item for item in items if needle in f"{item.athlete.first_name} {item.athlete.last_name}".lower()]
        severity_rank = {"high": 3, "warning": 2, "info": 1}
        if sort_by == "overdue_count":
            items.sort(key=lambda item: (-item.overdue_assignment_count, item.athlete.last_name))
        elif sort_by == "last_activity":
            items.sort(
                key=lambda item: item.last_qualifying_activity or datetime.min.replace(tzinfo=UTC),
                reverse=True,
            )
        elif sort_by == "name":
            items.sort(key=lambda item: (item.athlete.last_name, item.athlete.first_name))
        else:
            items.sort(
                key=lambda item: max(severity_rank[flag.severity] for flag in item.attention_flags),
                reverse=True,
            )
        total = len(items)
        start = (page - 1) * page_size
        return CoachAttentionPage(
            items=items[start : start + page_size],
            page=page,
            page_size=page_size,
            total=total,
            total_pages=ceil(total / page_size) if total else 0,
            data_completeness=self._combined_completeness(insights),
        )

    def _build(
        self,
        athletes: list[Athlete],
        coach_user_id: UUID,
        period: InsightPeriod,
        sections: set[str] | None,
    ) -> list[AthleteProgressInsights]:
        selected = sections or ALL_SECTIONS
        athlete_ids = [item.id for item in athletes]
        if not athlete_ids:
            return []
        query_start = period.previous_start or period.start
        local = self.queries.load(athlete_ids, query_start, period.end)
        review_available = media_available = True
        warnings: list[str] = []
        try:
            review_rows = self.review_client.fetch(
                athlete_ids, period.start, period.end, period.previous_start, period.previous_end
            ).items
        except Exception:
            review_rows = []
            review_available = False
            warnings.append("review_data_unavailable")
        try:
            media_rows = self.media_client.fetch(
                athlete_ids,
                coach_user_id,
                period.start,
                period.end,
                period.previous_start,
                period.previous_end,
            ).items
        except Exception:
            media_rows = []
            media_available = False
            warnings.append("media_data_unavailable")
        reviews_by_athlete = self._group(review_rows)
        media_by_athlete = {item.athlete_id: item for item in media_rows}
        generated_at = datetime.now(UTC)
        result = []
        for athlete in athletes:
            assignments = local.assignments.get(athlete.id, [])
            activities = local.activities.get(athlete.id, [])
            goals = local.goals.get(athlete.id, [])
            timeline = local.timeline.get(athlete.id, [])
            drills = DrillMetricsService().calculate(assignments, activities, period)
            goal_metrics = GoalMetricsService().calculate(goals, period)
            review_metrics = (
                ReviewInsightAggregationService().calculate(reviews_by_athlete.get(athlete.id, []), assignments, period)
                if review_available
                else None
            )
            media_metrics = media_by_athlete.get(athlete.id) if media_available else None
            activity = ActivityMetricsService().calculate(
                period,
                assignments,
                activities,
                goals,
                timeline,
                drills,
                goal_metrics,
                review_metrics,
                media_metrics,
            )
            attention = AttentionFlagService().calculate(
                assignments,
                goals,
                drills,
                review_metrics,
                activity,
                review_available,
                media_available,
                generated_at,
            )
            result.append(
                AthleteProgressInsights(
                    athlete=AthleteInsightSummary.model_validate(athlete, from_attributes=True),
                    period=self._period(period),
                    activity=activity if "activity" in selected else None,
                    drills=drills if "drills" in selected else None,
                    goals=goal_metrics if "goals" in selected else None,
                    reviews=review_metrics if "reviews" in selected else None,
                    attention_flags=attention if "attention" in selected else None,
                    trend_summaries=[drills.completion_trend, goal_metrics.completion_trend],
                    recent_milestones=[
                        RecentProgressItem(
                            athlete_id=athlete.id,
                            athlete_name=f"{athlete.first_name} {athlete.last_name}",
                            event_type=event.event_type,
                            title=event.title,
                            occurred_at=as_utc(event.occurred_at),
                        )
                        for event in timeline
                        if period.start <= as_utc(event.occurred_at) < period.end
                    ][:5],
                    data_completeness=DataCompleteness(
                        review_data_available=review_available,
                        media_data_available=media_available,
                        partial=not review_available or not media_available,
                        warnings=warnings,
                    ),
                    generated_at=generated_at,
                )
            )
        return result

    @staticmethod
    def _group(items: list[ApprovedReviewInsight]) -> dict[UUID, list[ApprovedReviewInsight]]:
        grouped: dict[UUID, list[ApprovedReviewInsight]] = {}
        for item in items:
            grouped.setdefault(item.athlete_id, []).append(item)
        return grouped

    @staticmethod
    def _period(period: InsightPeriod) -> InsightPeriodResponse:
        return InsightPeriodResponse(
            range=period.range_code,
            timezone=period.timezone,
            start=period.start,
            end=period.end,
            previous_start=period.previous_start,
            previous_end=period.previous_end,
        )

    @staticmethod
    def _attention_item(item: AthleteProgressInsights) -> CoachAttentionItem:
        return CoachAttentionItem(
            athlete=item.athlete,
            attention_flags=item.attention_flags or [],
            overdue_assignment_count=item.drills.current.overdue_count if item.drills else 0,
            active_assignment_count=item.drills.current.active_count if item.drills else 0,
            last_qualifying_activity=item.activity.last_qualifying_activity if item.activity else None,
            latest_approved_feedback_date=item.reviews.latest_approved_at if item.reviews else None,
            next_goal_due_date=item.goals.current.next_due_date if item.goals else None,
        )

    @staticmethod
    def _combined_completeness(insights: list[AthleteProgressInsights]) -> DataCompleteness:
        review = all(item.data_completeness.review_data_available for item in insights)
        media = all(item.data_completeness.media_data_available for item in insights)
        warnings = sorted({warning for item in insights for warning in item.data_completeness.warnings})
        return DataCompleteness(
            review_data_available=review,
            media_data_available=media,
            partial=not review or not media,
            warnings=warnings,
        )
