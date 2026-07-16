"""Coach-facing progress insight response contracts."""

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.enums import AthleteStatus, Position

TrendDirection = Literal["improving", "stable", "declining", "insufficient_data"]
MentionTrendDirection = Literal["increasing", "stable", "decreasing", "insufficient_data"]
AttentionSeverity = Literal["info", "warning", "high"]


class InsightPeriodResponse(BaseModel):
    range: str
    timezone: str
    start: datetime
    end: datetime
    previous_start: datetime | None
    previous_end: datetime | None
    boundary_policy: Literal["start_inclusive_end_exclusive"] = "start_inclusive_end_exclusive"


class DataCompleteness(BaseModel):
    review_data_available: bool
    media_data_available: bool
    partial: bool
    warnings: list[str] = Field(default_factory=list)


class CountComparison(BaseModel):
    current: int
    previous: int | None
    absolute_change: int | None


class RateTrend(BaseModel):
    current_value: float | None
    previous_value: float | None
    absolute_change: float | None
    percentage_point_change: float | None
    direction: TrendDirection
    current_sample_size: int
    previous_sample_size: int


class TimeSeriesPoint(BaseModel):
    period_start: date
    value: int


class ActivitySummary(BaseModel):
    practice_sessions_created: CountComparison
    practice_sessions_completed: CountComparison
    videos_uploaded: CountComparison
    approved_reviews: CountComparison
    drills_assigned: CountComparison
    drills_started: CountComparison
    drills_completed: CountComparison
    goals_created: CountComparison
    goals_completed: CountComparison
    athlete_visible_timeline_events: CountComparison
    last_qualifying_activity: datetime | None


class DrillPeriodMetrics(BaseModel):
    assigned_count: int
    started_count: int
    completed_count: int
    completed_during_period: int
    cancelled_count: int
    active_count: int
    in_progress_count: int
    overdue_count: int
    completion_rate: float | None
    completion_rate_sample_size: int
    on_time_completion_rate: float | None
    on_time_sample_size: int
    average_completion_days: float | None
    median_completion_days: float | None
    average_progress_percentage: float | None
    assignments_due_next_7_days: int


class DrillMetrics(BaseModel):
    current: DrillPeriodMetrics
    previous: DrillPeriodMetrics | None
    completion_trend: RateTrend
    weekly_completions: list[TimeSeriesPoint]


class GoalPeriodMetrics(BaseModel):
    active_count: int
    completed_count: int
    paused_count: int
    cancelled_count: int
    created_during_period: int
    completed_during_period: int
    completion_rate: float | None
    completion_rate_sample_size: int
    due_next_14_days: int
    overdue_count: int
    next_due_date: date | None
    category_distribution: dict[str, int]
    priority_distribution: dict[str, int]


class GoalMetrics(BaseModel):
    current: GoalPeriodMetrics
    previous: GoalPeriodMetrics | None
    completion_trend: RateTrend
    weekly_completions: list[TimeSeriesPoint]


class RecurringInsightItem(BaseModel):
    key: str
    display_label: str
    taxonomy_code: str | None
    occurrence_count: int
    distinct_review_count: int
    first_seen_at: datetime
    last_seen_at: datetime
    high_priority_count: int = 0
    related_review_ids: list[UUID]
    related_assignment_count: int = 0
    current_mentions: int
    previous_mentions: int
    trend: MentionTrendDirection


class ReviewInsights(BaseModel):
    approved_review_count: CountComparison
    latest_approved_at: datetime | None
    review_type_distribution: dict[str, int]
    recurring_improvement_areas: list[RecurringInsightItem]
    recurring_strengths: list[RecurringInsightItem]
    weekly_approved_reviews: list[TimeSeriesPoint]


class AttentionFlag(BaseModel):
    code: str
    severity: AttentionSeverity
    title: str
    description: str
    source: str
    detected_at: datetime
    related_entity_ids: list[UUID] = Field(default_factory=list)
    recommended_action: str | None = None


class AthleteInsightSummary(BaseModel):
    id: UUID
    first_name: str
    last_name: str
    preferred_name: str | None
    primary_position: Position | None
    status: AthleteStatus


class RecentProgressItem(BaseModel):
    athlete_id: UUID
    athlete_name: str
    event_type: str
    title: str
    occurred_at: datetime


class AthleteProgressInsights(BaseModel):
    athlete: AthleteInsightSummary
    period: InsightPeriodResponse
    activity: ActivitySummary | None = None
    drills: DrillMetrics | None = None
    goals: GoalMetrics | None = None
    reviews: ReviewInsights | None = None
    attention_flags: list[AttentionFlag] | None = None
    trend_summaries: list[RateTrend] = Field(default_factory=list)
    recent_milestones: list[RecentProgressItem] = Field(default_factory=list)
    data_completeness: DataCompleteness
    generated_at: datetime


class CoachInsightsResponse(BaseModel):
    period: InsightPeriodResponse
    active_athlete_count: int
    athletes_with_attention_flags: int
    total_overdue_assignments: int
    total_active_assignments: int
    completed_drills_during_period: int
    approved_reviews_during_period: int | None
    completed_practice_sessions_during_period: int | None
    top_recurring_improvement_areas: list[RecurringInsightItem]
    recent_progress_items: list[RecentProgressItem]
    attention_items: list["CoachAttentionItem"]
    attention_page: int
    attention_page_size: int
    attention_total: int
    attention_total_pages: int
    data_completeness: DataCompleteness
    generated_at: datetime


class CoachAttentionItem(BaseModel):
    athlete: AthleteInsightSummary
    attention_flags: list[AttentionFlag]
    overdue_assignment_count: int
    active_assignment_count: int
    last_qualifying_activity: datetime | None
    latest_approved_feedback_date: datetime | None
    next_goal_due_date: date | None


class CoachAttentionPage(BaseModel):
    items: list[CoachAttentionItem]
    page: int
    page_size: int
    total: int
    total_pages: int
    data_completeness: DataCompleteness
