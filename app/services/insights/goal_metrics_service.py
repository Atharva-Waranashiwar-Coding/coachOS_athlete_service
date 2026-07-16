"""Explicit athlete goal metric formulas."""

from collections import Counter, defaultdict
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from app.core.insight_rules import InsightPeriod, as_utc
from app.models.enums import GoalStatus
from app.models.goal import AthleteGoal
from app.schemas.insights import GoalMetrics, GoalPeriodMetrics, TimeSeriesPoint
from app.services.insights.trend_comparison_service import TrendComparisonService


class GoalMetricsService:
    def calculate(self, goals: list[AthleteGoal], period: InsightPeriod) -> GoalMetrics:
        current = self._period(goals, period.start, period.end, period)
        previous = (
            self._period(goals, period.previous_start, period.previous_end, period)
            if period.previous_start and period.previous_end
            else None
        )
        return GoalMetrics(
            current=current,
            previous=previous,
            completion_trend=TrendComparisonService.rate(
                current.completion_rate,
                previous.completion_rate if previous else None,
                current.completion_rate_sample_size,
                previous.completion_rate_sample_size if previous else 0,
            ),
            weekly_completions=self._weekly(goals, period),
        )

    def _period(
        self,
        goals: list[AthleteGoal],
        start: datetime,
        end: datetime,
        period: InsightPeriod,
    ) -> GoalPeriodMetrics:
        eligible = [item for item in goals if as_utc(item.created_at) < end]
        cancelled = [item for item in eligible if item.status == GoalStatus.CANCELLED and as_utc(item.updated_at) < end]
        denominator = [item for item in eligible if item not in cancelled]
        completed = [item for item in denominator if item.completed_at and as_utc(item.completed_at) < end]
        active = [
            item
            for item in denominator
            if (not item.completed_at or as_utc(item.completed_at) >= end)
            and item.status not in {GoalStatus.PAUSED, GoalStatus.CANCELLED}
        ]
        paused = [
            item
            for item in denominator
            if item.status == GoalStatus.PAUSED and as_utc(item.updated_at) < end and not item.completed_at
        ]
        end_date = end.astimezone(ZoneInfo(period.timezone)).date()
        categories = Counter(item.category.value for item in denominator)
        priorities = Counter(str(item.priority) for item in denominator)
        upcoming_dates = sorted(
            item.target_date for item in active if item.target_date and item.target_date >= end_date
        )
        return GoalPeriodMetrics(
            active_count=len(active),
            completed_count=len(completed),
            paused_count=len(paused),
            cancelled_count=len(cancelled),
            created_during_period=sum(start <= as_utc(item.created_at) < end for item in goals),
            completed_during_period=sum(
                bool(item.completed_at and start <= as_utc(item.completed_at) < end) for item in goals
            ),
            completion_rate=round(len(completed) / len(denominator) * 100, 1) if denominator else None,
            completion_rate_sample_size=len(denominator),
            due_next_14_days=sum(
                bool(item.target_date and end_date <= item.target_date < end_date + timedelta(days=14))
                for item in active
            ),
            overdue_count=sum(bool(item.target_date and item.target_date < end_date) for item in active),
            next_due_date=upcoming_dates[0] if upcoming_dates else None,
            category_distribution=dict(categories),
            priority_distribution=dict(priorities),
        )

    @staticmethod
    def _weekly(goals: list[AthleteGoal], period: InsightPeriod) -> list[TimeSeriesPoint]:
        zone = ZoneInfo(period.timezone)
        counts: dict = defaultdict(int)
        for item in goals:
            if item.completed_at and period.start <= as_utc(item.completed_at) < period.end:
                local_date = as_utc(item.completed_at).astimezone(zone).date()
                week = local_date - timedelta(days=local_date.weekday())
                counts[week] += 1
        return [TimeSeriesPoint(period_start=key, value=counts[key]) for key in sorted(counts)]
