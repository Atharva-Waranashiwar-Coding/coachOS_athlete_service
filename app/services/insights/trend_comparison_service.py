"""Deterministic rate and mention trend comparisons."""

from app.core.config import settings
from app.schemas.insights import MentionTrendDirection, RateTrend, TrendDirection


class TrendComparisonService:
    @staticmethod
    def rate(
        current: float | None,
        previous: float | None,
        current_sample: int,
        previous_sample: int,
    ) -> RateTrend:
        if (
            current is None
            or previous is None
            or current_sample < settings.insight_trend_min_sample_size
            or previous_sample < settings.insight_trend_min_sample_size
        ):
            direction: TrendDirection = "insufficient_data"
            change = None
        else:
            change = round(current - previous, 1)
            threshold = settings.insight_trend_threshold_percentage_points
            direction = "improving" if change >= threshold else "declining" if change <= -threshold else "stable"
        return RateTrend(
            current_value=current,
            previous_value=previous,
            absolute_change=change,
            percentage_point_change=change,
            direction=direction,
            current_sample_size=current_sample,
            previous_sample_size=previous_sample,
        )

    @staticmethod
    def mentions(current: int, previous: int) -> MentionTrendDirection:
        if (
            current < settings.insight_recurring_area_min_reviews
            or previous < settings.insight_recurring_area_min_reviews
        ):
            return "insufficient_data"
        if current > previous:
            return "increasing"
        if current < previous:
            return "decreasing"
        return "stable"
