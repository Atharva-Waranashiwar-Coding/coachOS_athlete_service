"""Add coach drill libraries and athlete assignments."""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20260716_0003"
down_revision = "20260710_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    category = postgresql.ENUM(
        "hitting",
        "pitching",
        "fielding",
        "throwing",
        "catching",
        "footwork",
        "speed",
        "strength",
        "mobility",
        "conditioning",
        "recovery",
        "mental",
        "general",
        name="drill_category",
        create_type=False,
    )
    difficulty = postgresql.ENUM("beginner", "intermediate", "advanced", name="drill_difficulty", create_type=False)
    visibility = postgresql.ENUM("private", "organization", "system", name="drill_visibility", create_type=False)
    drill_status = postgresql.ENUM("active", "archived", name="drill_status", create_type=False)
    assignment_status = postgresql.ENUM(
        "assigned",
        "in_progress",
        "completed",
        "cancelled",
        name="drill_assignment_status",
        create_type=False,
    )
    activity_type = postgresql.ENUM(
        "assigned",
        "started",
        "updated",
        "progress_updated",
        "completed",
        "cancelled",
        name="drill_activity_type",
        create_type=False,
    )
    for enum in (category, difficulty, visibility, drill_status, assignment_status, activity_type):
        enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "drills",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("created_by_user_id", sa.UUID(), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("instructions", sa.Text(), nullable=False),
        sa.Column("category", category, nullable=False),
        sa.Column("sport", sa.String(50), nullable=False, server_default="baseball"),
        sa.Column("difficulty", difficulty, nullable=False),
        sa.Column("equipment", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("estimated_duration_minutes", sa.Integer()),
        sa.Column("default_sets", sa.Integer()),
        sa.Column("default_repetitions", sa.Integer()),
        sa.Column("default_frequency", sa.String(200)),
        sa.Column("tags", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("video_url", sa.String(2000)),
        sa.Column("visibility", visibility, nullable=False, server_default="private"),
        sa.Column("status", drill_status, nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint(
            "estimated_duration_minutes IS NULL OR estimated_duration_minutes > 0", name="ck_drill_duration"
        ),
        sa.CheckConstraint("default_sets IS NULL OR default_sets > 0", name="ck_drill_sets"),
        sa.CheckConstraint("default_repetitions IS NULL OR default_repetitions > 0", name="ck_drill_repetitions"),
    )
    for name, columns in (
        ("ix_drills_created_by", ["created_by_user_id"]),
        ("ix_drills_category", ["category"]),
        ("ix_drills_difficulty", ["difficulty"]),
        ("ix_drills_status", ["status"]),
    ):
        op.create_index(name, "drills", columns)
    op.create_index("ix_drills_lower_title", "drills", [sa.text("lower(title)")])
    op.create_index("ix_drills_tags_gin", "drills", ["tags"], postgresql_using="gin")

    op.create_table(
        "drill_assignments",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("athlete_id", sa.UUID(), sa.ForeignKey("athletes.id"), nullable=False),
        sa.Column("drill_id", sa.UUID(), sa.ForeignKey("drills.id")),
        sa.Column("assigned_by_user_id", sa.UUID(), nullable=False),
        sa.Column("source_review_id", sa.UUID()),
        sa.Column("source_recommendation_index", sa.Integer()),
        sa.Column("title_snapshot", sa.String(200), nullable=False),
        sa.Column("description_snapshot", sa.Text()),
        sa.Column("instructions_snapshot", sa.Text(), nullable=False),
        sa.Column("coach_notes", sa.Text()),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("status", assignment_status, nullable=False, server_default="assigned"),
        sa.Column("assigned_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("start_date", sa.Date()),
        sa.Column("due_date", sa.Date()),
        sa.Column("target_sets", sa.Integer()),
        sa.Column("target_repetitions", sa.Integer()),
        sa.Column("target_duration_minutes", sa.Integer()),
        sa.Column("frequency", sa.String(200)),
        sa.Column("completion_percentage", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("actual_sets", sa.Integer()),
        sa.Column("actual_repetitions", sa.Integer()),
        sa.Column("actual_duration_minutes", sa.Integer()),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("cancelled_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("priority BETWEEN 1 AND 5", name="ck_assignment_priority"),
        sa.CheckConstraint("completion_percentage BETWEEN 0 AND 100", name="ck_assignment_progress"),
        sa.CheckConstraint(
            "source_review_id IS NULL = (source_recommendation_index IS NULL)", name="ck_assignment_review_source_pair"
        ),
        sa.CheckConstraint(
            "source_recommendation_index IS NULL OR source_recommendation_index >= 0",
            name="ck_assignment_recommendation_index",
        ),
        sa.CheckConstraint(
            "start_date IS NULL OR due_date IS NULL OR due_date >= start_date", name="ck_assignment_dates"
        ),
        sa.CheckConstraint("target_sets IS NULL OR target_sets > 0", name="ck_assignment_target_sets"),
        sa.CheckConstraint(
            "target_repetitions IS NULL OR target_repetitions > 0", name="ck_assignment_target_repetitions"
        ),
        sa.CheckConstraint(
            "target_duration_minutes IS NULL OR target_duration_minutes > 0", name="ck_assignment_target_duration"
        ),
        sa.CheckConstraint(
            "status != 'completed' OR (completion_percentage = 100 AND completed_at IS NOT NULL)",
            name="ck_assignment_completed_state",
        ),
        sa.CheckConstraint(
            "status != 'cancelled' OR (cancelled_at IS NOT NULL AND completed_at IS NULL)",
            name="ck_assignment_cancelled_state",
        ),
    )
    for name, columns in (
        ("ix_assignments_athlete", ["athlete_id"]),
        ("ix_assignments_assigned_by", ["assigned_by_user_id"]),
        ("ix_assignments_status", ["status"]),
        ("ix_assignments_due_date", ["due_date"]),
        ("ix_assignments_source_review", ["source_review_id"]),
        ("ix_assignments_drill", ["drill_id"]),
        ("ix_assignments_athlete_status", ["athlete_id", "status"]),
        ("ix_assignments_athlete_assigned", ["athlete_id", "assigned_at"]),
    ):
        op.create_index(name, "drill_assignments", columns)

    op.create_table(
        "drill_assignment_activities",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column(
            "assignment_id", sa.UUID(), sa.ForeignKey("drill_assignments.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("actor_user_id", sa.UUID(), nullable=False),
        sa.Column("event_type", activity_type, nullable=False),
        sa.Column("notes", sa.Text()),
        sa.Column("progress_value", sa.Integer()),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_drill_assignment_activities_assignment_id", "drill_assignment_activities", ["assignment_id"])


def downgrade() -> None:
    op.drop_table("drill_assignment_activities")
    op.drop_table("drill_assignments")
    op.drop_table("drills")
    for name in (
        "drill_activity_type",
        "drill_assignment_status",
        "drill_status",
        "drill_visibility",
        "drill_difficulty",
        "drill_category",
    ):
        postgresql.ENUM(name=name).drop(op.get_bind(), checkfirst=True)
