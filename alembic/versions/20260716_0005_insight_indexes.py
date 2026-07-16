"""Add aggregation indexes for Stage 10 progress insights."""

from collections.abc import Sequence

from alembic import op

revision: str = "20260716_0005"
down_revision: str | None = "20260716_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "ix_assignments_athlete_due_status",
        "drill_assignments",
        ["athlete_id", "due_date", "status"],
    )
    op.create_index(
        "ix_assignments_athlete_completed",
        "drill_assignments",
        ["athlete_id", "completed_at"],
    )
    op.create_index(
        "ix_goals_athlete_target_status",
        "athlete_goals",
        ["athlete_id", "target_date", "status"],
    )
    op.create_index(
        "ix_goals_athlete_completed",
        "athlete_goals",
        ["athlete_id", "completed_at"],
    )
    op.create_index(
        "ix_timeline_athlete_visibility_occurred",
        "timeline_events",
        ["athlete_id", "visibility", "occurred_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_timeline_athlete_visibility_occurred", table_name="timeline_events")
    op.drop_index("ix_goals_athlete_completed", table_name="athlete_goals")
    op.drop_index("ix_goals_athlete_target_status", table_name="athlete_goals")
    op.drop_index("ix_assignments_athlete_completed", table_name="drill_assignments")
    op.drop_index("ix_assignments_athlete_due_status", table_name="drill_assignments")
