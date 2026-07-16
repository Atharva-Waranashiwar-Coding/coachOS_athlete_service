"""Deterministic coach workflow attention flags."""

from datetime import UTC, date, datetime, timedelta

from app.core.config import settings
from app.models.drill_assignment import DrillAssignment
from app.models.enums import DrillAssignmentStatus, GoalStatus
from app.models.goal import AthleteGoal
from app.schemas.insights import (
    ActivitySummary,
    AttentionFlag,
    AttentionSeverity,
    DrillMetrics,
    ReviewInsights,
)


class AttentionFlagService:
    def calculate(
        self,
        assignments: list[DrillAssignment],
        goals: list[AthleteGoal],
        drills: DrillMetrics,
        reviews: ReviewInsights | None,
        activity: ActivitySummary,
        review_available: bool,
        media_available: bool,
        generated_at: datetime,
    ) -> list[AttentionFlag]:
        flags: list[AttentionFlag] = []
        overdue = [
            item
            for item in assignments
            if item.status not in {DrillAssignmentStatus.COMPLETED, DrillAssignmentStatus.CANCELLED}
            and item.due_date
            and item.due_date < date.today()
        ]
        if overdue:
            flags.append(
                self._flag(
                    "overdue_drills",
                    "high" if len(overdue) >= 3 else "warning",
                    "Overdue drill assignments",
                    f"{len(overdue)} drill assignment(s) are past due.",
                    "drills",
                    generated_at,
                    [item.id for item in overdue],
                    "Review priorities and adjust due dates where appropriate.",
                )
            )
        active = [
            item
            for item in assignments
            if item.status in {DrillAssignmentStatus.ASSIGNED, DrillAssignmentStatus.IN_PROGRESS}
        ]
        if len(active) >= settings.insight_incomplete_assignment_threshold:
            flags.append(
                self._flag(
                    "multiple_incomplete_assignments",
                    "warning",
                    "Several active assignments",
                    f"{len(active)} assignments are currently incomplete.",
                    "drills",
                    generated_at,
                    [item.id for item in active],
                    "Confirm that the current workload is still appropriate.",
                )
            )
        if review_available and media_available:
            cutoff = generated_at - timedelta(days=settings.insight_low_activity_days)
            if not activity.last_qualifying_activity or activity.last_qualifying_activity < cutoff:
                flags.append(
                    self._flag(
                        "low_recent_activity",
                        "info",
                        "Limited recent activity",
                        f"No qualifying activity was recorded in the last {settings.insight_low_activity_days} days.",
                        "activity",
                        generated_at,
                    )
                )
        due_soon = [
            item
            for item in goals
            if item.status == GoalStatus.ACTIVE
            and item.target_date
            and date.today() <= item.target_date <= date.today() + timedelta(days=settings.insight_goal_due_soon_days)
        ]
        overdue_goals = [
            item
            for item in goals
            if item.status == GoalStatus.ACTIVE and item.target_date and item.target_date < date.today()
        ]
        if due_soon:
            flags.append(
                self._flag(
                    "goal_due_soon",
                    "info",
                    "Goal deadline approaching",
                    f"{len(due_soon)} active goal(s) are due soon.",
                    "goals",
                    generated_at,
                    [item.id for item in due_soon],
                )
            )
        if overdue_goals:
            flags.append(
                self._flag(
                    "goal_overdue",
                    "warning",
                    "Goal deadline passed",
                    f"{len(overdue_goals)} active goal(s) are past their target date.",
                    "goals",
                    generated_at,
                    [item.id for item in overdue_goals],
                    "Review the goal status or target date.",
                )
            )
        if reviews:
            repeated = [
                item
                for item in reviews.recurring_improvement_areas
                if item.high_priority_count >= settings.insight_repeated_area_review_threshold
            ]
            for item in repeated:
                flags.append(
                    self._flag(
                        "repeated_high_priority_area",
                        "warning",
                        "Repeated high-priority feedback area",
                        f"{item.display_label} was mentioned as high priority in multiple approved reviews.",
                        "reviews",
                        generated_at,
                        item.related_review_ids,
                        "Inspect the approved feedback and related assignments.",
                    )
                )
        if review_available and media_available:
            recent_practice = activity.practice_sessions_completed.current > 0
            latest_review = self._latest_review(reviews)
            if recent_practice and (
                not latest_review or latest_review < generated_at - timedelta(days=settings.insight_no_feedback_days)
            ):
                flags.append(
                    self._flag(
                        "no_recent_approved_feedback",
                        "info",
                        "Recent practice has no approved feedback",
                        "Practice activity exists without a recently approved coach review.",
                        "reviews",
                        generated_at,
                        recommended_action="Review recent practice records when useful.",
                    )
                )
        order = {"high": 0, "warning": 1, "info": 2}
        return sorted(flags, key=lambda item: (order[item.severity], item.code))

    @staticmethod
    def _latest_review(reviews: ReviewInsights | None) -> datetime | None:
        return reviews.latest_approved_at if reviews else None

    @staticmethod
    def _flag(
        code: str,
        severity: AttentionSeverity,
        title: str,
        description: str,
        source: str,
        detected_at: datetime,
        related_entity_ids: list | None = None,
        recommended_action: str | None = None,
    ) -> AttentionFlag:
        return AttentionFlag(
            code=code,
            severity=severity,
            title=title,
            description=description,
            source=source,
            detected_at=detected_at.astimezone(UTC),
            related_entity_ids=related_entity_ids or [],
            recommended_action=recommended_action,
        )
