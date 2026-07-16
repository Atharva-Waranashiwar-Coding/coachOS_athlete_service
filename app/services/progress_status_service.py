"""Deterministic athlete progress status rules without AI scoring."""

from datetime import UTC, datetime, timedelta

from app.schemas.athlete_self import ProgressStatusResponse


class ProgressStatusService:
    @staticmethod
    def calculate(
        *,
        active_assignments: int,
        overdue_assignments: int,
        completed_assignments: int,
        activated_at: datetime | None,
    ) -> ProgressStatusResponse:
        if overdue_assignments > 0:
            return ProgressStatusResponse(
                code="needs_attention",
                label="Needs attention",
                reason="You have one or more overdue drill assignments.",
            )
        if active_assignments > 0:
            return ProgressStatusResponse(
                code="on_track",
                label="On track",
                reason="You have active drills and no overdue assignments.",
            )
        if activated_at:
            value = activated_at if activated_at.tzinfo else activated_at.replace(tzinfo=UTC)
            if value >= datetime.now(UTC) - timedelta(days=14) and completed_assignments == 0:
                return ProgressStatusResponse(
                    code="getting_started",
                    label="Getting started",
                    reason="Your account is new and your first training activity is ready to begin.",
                )
        return ProgressStatusResponse(
            code="no_current_assignments",
            label="No current assignments",
            reason="You do not have assigned or in-progress drills right now.",
        )
