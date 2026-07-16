"""Explicit drill assignment metric formulas."""

from collections import defaultdict
from datetime import datetime, timedelta
from statistics import mean, median
from zoneinfo import ZoneInfo

from app.core.insight_rules import InsightPeriod, as_utc
from app.models.drill_assignment import DrillAssignment
from app.models.drill_assignment_activity import DrillAssignmentActivity
from app.models.enums import DrillActivityType
from app.schemas.insights import DrillMetrics, DrillPeriodMetrics, TimeSeriesPoint
from app.services.insights.trend_comparison_service import TrendComparisonService


class DrillMetricsService:
    def calculate(
        self,
        assignments: list[DrillAssignment],
        activities: list[DrillAssignmentActivity],
        period: InsightPeriod,
    ) -> DrillMetrics:
        current = self._period(assignments, activities, period.start, period.end, period)
        previous = (
            self._period(assignments, activities, period.previous_start, period.previous_end, period)
            if period.previous_start and period.previous_end
            else None
        )
        trend = TrendComparisonService.rate(
            current.completion_rate,
            previous.completion_rate if previous else None,
            current.completion_rate_sample_size,
            previous.completion_rate_sample_size if previous else 0,
        )
        return DrillMetrics(
            current=current,
            previous=previous,
            completion_trend=trend,
            weekly_completions=self._weekly(assignments, period),
        )

    def _period(
        self,
        assignments: list[DrillAssignment],
        activities: list[DrillAssignmentActivity],
        start: datetime,
        end: datetime,
        period: InsightPeriod,
    ) -> DrillPeriodMetrics:
        eligible = [item for item in assignments if as_utc(item.assigned_at) < end]
        assigned = [item for item in eligible if start <= as_utc(item.assigned_at) < end]
        started_ids = {
            item.assignment_id
            for item in activities
            if start <= as_utc(item.occurred_at) < end and item.event_type == DrillActivityType.STARTED
        }
        completed_period = [item for item in eligible if item.completed_at and start <= as_utc(item.completed_at) < end]
        cancelled_period = [item for item in eligible if item.cancelled_at and start <= as_utc(item.cancelled_at) < end]
        denominator = [item for item in eligible if not item.cancelled_at or as_utc(item.cancelled_at) >= end]
        completed_by_end = [item for item in denominator if item.completed_at and as_utc(item.completed_at) < end]
        active = [item for item in denominator if not item.completed_at or as_utc(item.completed_at) >= end]
        activity_by_assignment: dict = defaultdict(list)
        for item in activities:
            if as_utc(item.occurred_at) < end:
                activity_by_assignment[item.assignment_id].append(item)
        in_progress = [
            item
            for item in active
            if any(
                activity.event_type in {DrillActivityType.STARTED, DrillActivityType.PROGRESS_UPDATED}
                for activity in activity_by_assignment[item.id]
            )
        ]
        end_date = end.astimezone(ZoneInfo(period.timezone)).date()
        overdue = [item for item in active if item.due_date and item.due_date < end_date]
        due_next = [
            item for item in active if item.due_date and end_date <= item.due_date < end_date + timedelta(days=7)
        ]
        due_completions = [item for item in completed_period if item.due_date is not None]
        on_time = [
            item
            for item in due_completions
            if item.completed_at and item.due_date is not None and item.completed_at.date() <= item.due_date
        ]
        durations = [
            (as_utc(item.completed_at) - as_utc(item.assigned_at)).total_seconds() / 86400
            for item in completed_period
            if item.completed_at
        ]
        progress_values = [self._progress_at(item, activity_by_assignment[item.id], end) for item in active]
        return DrillPeriodMetrics(
            assigned_count=len(assigned),
            started_count=len(started_ids),
            completed_count=len(completed_by_end),
            completed_during_period=len(completed_period),
            cancelled_count=len(cancelled_period),
            active_count=len(active),
            in_progress_count=len(in_progress),
            overdue_count=len(overdue),
            completion_rate=round(len(completed_by_end) / len(denominator) * 100, 1) if denominator else None,
            completion_rate_sample_size=len(denominator),
            on_time_completion_rate=(round(len(on_time) / len(due_completions) * 100, 1) if due_completions else None),
            on_time_sample_size=len(due_completions),
            average_completion_days=round(mean(durations), 1) if durations else None,
            median_completion_days=round(median(durations), 1) if durations else None,
            average_progress_percentage=round(mean(progress_values), 1) if progress_values else None,
            assignments_due_next_7_days=len(due_next),
        )

    @staticmethod
    def _progress_at(
        assignment: DrillAssignment,
        activities: list[DrillAssignmentActivity],
        end: datetime,
    ) -> int:
        if assignment.completed_at and as_utc(assignment.completed_at) < end:
            return 100
        values = [
            (as_utc(item.occurred_at), item.progress_value)
            for item in activities
            if as_utc(item.occurred_at) < end and item.progress_value is not None
        ]
        return max(values, default=(end, 0), key=lambda item: item[0])[1] or 0

    @staticmethod
    def _weekly(assignments: list[DrillAssignment], period: InsightPeriod) -> list[TimeSeriesPoint]:
        zone = ZoneInfo(period.timezone)
        counts: dict = defaultdict(int)
        for item in assignments:
            if item.completed_at and period.start <= as_utc(item.completed_at) < period.end:
                local_date = as_utc(item.completed_at).astimezone(zone).date()
                week = local_date - timedelta(days=local_date.weekday())
                counts[week] += 1
        return [TimeSeriesPoint(period_start=key, value=counts[key]) for key in sorted(counts)]
