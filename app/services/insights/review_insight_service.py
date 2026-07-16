"""Recurring strength and improvement-area normalization and aggregation."""

import json
import re
from collections import Counter, defaultdict
from datetime import timedelta
from pathlib import Path
from uuid import UUID
from zoneinfo import ZoneInfo

from app.core.config import settings
from app.core.insight_rules import InsightPeriod
from app.integrations.review_insights import ApprovedReviewInsight, ReviewInsightLabel
from app.models.drill_assignment import DrillAssignment
from app.schemas.insights import (
    CountComparison,
    RecurringInsightItem,
    ReviewInsights,
    TimeSeriesPoint,
)
from app.services.insights.trend_comparison_service import TrendComparisonService

VALID_TAXONOMY = re.compile(r"^[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)+$")


class InsightLabelNormalizer:
    def __init__(self) -> None:
        payload = json.loads((Path(__file__).parents[2] / "core" / "insight_aliases.v1.json").read_text())
        self.aliases: dict[str, str] = payload["aliases"]

    def normalize(self, item: ReviewInsightLabel) -> tuple[str, str | None]:
        if item.taxonomy_code and VALID_TAXONOMY.fullmatch(item.taxonomy_code):
            return item.taxonomy_code, item.taxonomy_code
        title = re.sub(r"[^\w\s-]", "", item.title.lower())
        normalized = " ".join(title.split())
        alias = self.aliases.get(normalized)
        return (alias, alias) if alias else (normalized, None)


class ReviewInsightAggregationService:
    def __init__(self) -> None:
        self.normalizer = InsightLabelNormalizer()

    def calculate(
        self,
        reviews: list[ApprovedReviewInsight],
        assignments: list[DrillAssignment],
        period: InsightPeriod,
    ) -> ReviewInsights:
        current = [item for item in reviews if period.start <= item.approved_at < period.end]
        previous = [
            item
            for item in reviews
            if period.previous_start
            and period.previous_end
            and period.previous_start <= item.approved_at < period.previous_end
        ]
        return ReviewInsights(
            approved_review_count=CountComparison(
                current=len(current),
                previous=len(previous) if period.previous_start else None,
                absolute_change=len(current) - len(previous) if period.previous_start else None,
            ),
            latest_approved_at=max((item.approved_at for item in current), default=None),
            review_type_distribution=dict(Counter(item.review_type for item in current)),
            recurring_improvement_areas=self._aggregate(current, previous, "improvement_areas", assignments),
            recurring_strengths=self._aggregate(current, previous, "strengths", assignments),
            weekly_approved_reviews=self._weekly(current, period),
        )

    def _aggregate(
        self,
        current: list[ApprovedReviewInsight],
        previous: list[ApprovedReviewInsight],
        field: str,
        assignments: list[DrillAssignment],
    ) -> list[RecurringInsightItem]:
        current_items = self._review_mentions(current, field)
        previous_items = self._review_mentions(previous, field)
        result = []
        for key, mentions in current_items.items():
            distinct = len(mentions)
            if distinct < settings.insight_recurring_area_min_reviews:
                continue
            previous_count = len(previous_items.get(key, []))
            all_occurrences = [entry for entries in mentions.values() for entry in entries]
            review_ids = sorted(mentions, key=str)
            taxonomy = next((entry.taxonomy_code for entry in all_occurrences if entry.taxonomy_code), None)
            display = next(entry.title for entry in all_occurrences)
            review_dates = {item.review_id: item.approved_at for item in current if item.review_id in mentions}
            result.append(
                RecurringInsightItem(
                    key=key,
                    display_label=display,
                    taxonomy_code=taxonomy,
                    occurrence_count=sum(len(entries) for entries in mentions.values()),
                    distinct_review_count=distinct,
                    first_seen_at=min(review_dates.values()),
                    last_seen_at=max(review_dates.values()),
                    high_priority_count=sum(
                        any(entry.priority == "high" for entry in entries) for entries in mentions.values()
                    ),
                    related_review_ids=review_ids,
                    related_assignment_count=sum(item.source_review_id in mentions for item in assignments),
                    current_mentions=distinct,
                    previous_mentions=previous_count,
                    trend=TrendComparisonService.mentions(distinct, previous_count),
                )
            )
        return sorted(result, key=lambda item: (-item.distinct_review_count, item.display_label.lower()))

    def _review_mentions(
        self,
        reviews: list[ApprovedReviewInsight],
        field: str,
    ) -> dict[str, dict[UUID, list[ReviewInsightLabel]]]:
        result: dict[str, dict[UUID, list[ReviewInsightLabel]]] = defaultdict(dict)
        for review in reviews:
            grouped: dict[str, list[ReviewInsightLabel]] = defaultdict(list)
            for item in getattr(review, field):
                key, taxonomy = self.normalizer.normalize(item)
                if taxonomy and not item.taxonomy_code:
                    item = item.model_copy(update={"taxonomy_code": taxonomy})
                grouped[key].append(item)
            for key, entries in grouped.items():
                result[key][review.review_id] = entries
        return result

    @staticmethod
    def _weekly(reviews: list[ApprovedReviewInsight], period: InsightPeriod) -> list[TimeSeriesPoint]:
        zone = ZoneInfo(period.timezone)
        counts: dict = defaultdict(int)
        for item in reviews:
            local_date = item.approved_at.astimezone(zone).date()
            week = local_date - timedelta(days=local_date.weekday())
            counts[week] += 1
        return [TimeSeriesPoint(period_start=key, value=counts[key]) for key in sorted(counts)]
