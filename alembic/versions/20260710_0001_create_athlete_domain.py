"""create athlete domain tables

Revision ID: 20260710_0001
Revises:
Create Date: 2026-07-10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260710_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _create_enum(name: str, values: tuple[str, ...]) -> postgresql.ENUM:
    enum_type = postgresql.ENUM(*values, name=name, create_type=False)
    enum_type.create(op.get_bind(), checkfirst=True)
    return enum_type


def upgrade() -> None:
    """Create athlete domain tables, constraints, and indexes."""
    position = _create_enum(
        "position",
        (
            "pitcher",
            "catcher",
            "first_base",
            "second_base",
            "third_base",
            "shortstop",
            "left_field",
            "center_field",
            "right_field",
            "utility",
        ),
    )
    bat_side = _create_enum("bat_side", ("left", "right", "switch"))
    throw_side = _create_enum("throw_side", ("left", "right"))
    athlete_status = _create_enum("athlete_status", ("active", "inactive", "archived"))
    relationship_role = _create_enum("relationship_role", ("primary_coach", "assistant_coach", "viewer"))
    relationship_status = _create_enum("relationship_status", ("active", "inactive"))
    goal_category = _create_enum(
        "goal_category",
        ("hitting", "pitching", "fielding", "strength", "speed", "mobility", "mental", "recruiting", "general"),
    )
    goal_status = _create_enum("goal_status", ("active", "completed", "paused", "cancelled"))

    op.create_table(
        "athletes",
        sa.Column("id", sa.UUID(), primary_key=True, nullable=False),
        sa.Column("first_name", sa.String(length=100), nullable=False),
        sa.Column("last_name", sa.String(length=100), nullable=False),
        sa.Column("preferred_name", sa.String(length=100), nullable=True),
        sa.Column("date_of_birth", sa.Date(), nullable=True),
        sa.Column("email", sa.String(length=320), nullable=True),
        sa.Column("phone", sa.String(length=50), nullable=True),
        sa.Column("primary_position", position, nullable=True),
        sa.Column("bats", bat_side, nullable=True),
        sa.Column("throws", throw_side, nullable=True),
        sa.Column("graduation_year", sa.Integer(), nullable=True),
        sa.Column("school_name", sa.String(length=200), nullable=True),
        sa.Column("team_name", sa.String(length=200), nullable=True),
        sa.Column("height_inches", sa.Integer(), nullable=True),
        sa.Column("weight_pounds", sa.Integer(), nullable=True),
        sa.Column("injury_notes", sa.Text(), nullable=True),
        sa.Column("general_notes", sa.Text(), nullable=True),
        sa.Column("status", athlete_status, nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_athletes_email", "athletes", ["email"])
    op.create_index("ix_athletes_status", "athletes", ["status"])
    op.create_index("ix_athletes_name", "athletes", ["last_name", "first_name"])
    op.create_index("ix_athletes_graduation_year", "athletes", ["graduation_year"])
    op.create_index("ix_athletes_primary_position", "athletes", ["primary_position"])

    op.create_table(
        "athlete_secondary_positions",
        sa.Column("athlete_id", sa.UUID(), sa.ForeignKey("athletes.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("position", position, primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "coach_athlete_relationships",
        sa.Column("id", sa.UUID(), primary_key=True, nullable=False),
        sa.Column("coach_user_id", sa.UUID(), nullable=False),
        sa.Column("athlete_id", sa.UUID(), sa.ForeignKey("athletes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("relationship_role", relationship_role, nullable=False),
        sa.Column("status", relationship_status, nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("coach_user_id", "athlete_id", name="uq_coach_athlete_relationship"),
    )
    op.create_index("ix_relationships_coach_user_id", "coach_athlete_relationships", ["coach_user_id"])
    op.create_index("ix_relationships_athlete_id", "coach_athlete_relationships", ["athlete_id"])

    op.create_table(
        "athlete_goals",
        sa.Column("id", sa.UUID(), primary_key=True, nullable=False),
        sa.Column("athlete_id", sa.UUID(), sa.ForeignKey("athletes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("category", goal_category, nullable=False),
        sa.Column("target_date", sa.Date(), nullable=True),
        sa.Column("status", goal_status, nullable=False, server_default="active"),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("created_by_user_id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("priority >= 1 AND priority <= 5", name="ck_goal_priority_range"),
    )
    op.create_index("ix_goals_athlete_status", "athlete_goals", ["athlete_id", "status"])

    op.create_table(
        "timeline_events",
        sa.Column("id", sa.UUID(), primary_key=True, nullable=False),
        sa.Column("athlete_id", sa.UUID(), sa.ForeignKey("athletes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("source_service", sa.String(length=100), nullable=False),
        sa.Column("source_entity_type", sa.String(length=100), nullable=True),
        sa.Column("source_entity_id", sa.String(length=100), nullable=True),
        sa.Column(
            "metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")
        ),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("created_by_user_id", sa.UUID(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_timeline_events_event_type", "timeline_events", ["event_type"])
    op.create_index("ix_timeline_athlete_occurred_at", "timeline_events", ["athlete_id", "occurred_at"])


def downgrade() -> None:
    """Drop athlete domain tables and enum types."""
    op.drop_index("ix_timeline_athlete_occurred_at", table_name="timeline_events")
    op.drop_index("ix_timeline_events_event_type", table_name="timeline_events")
    op.drop_table("timeline_events")
    op.drop_index("ix_goals_athlete_status", table_name="athlete_goals")
    op.drop_table("athlete_goals")
    op.drop_index("ix_relationships_athlete_id", table_name="coach_athlete_relationships")
    op.drop_index("ix_relationships_coach_user_id", table_name="coach_athlete_relationships")
    op.drop_table("coach_athlete_relationships")
    op.drop_table("athlete_secondary_positions")
    op.drop_index("ix_athletes_primary_position", table_name="athletes")
    op.drop_index("ix_athletes_graduation_year", table_name="athletes")
    op.drop_index("ix_athletes_name", table_name="athletes")
    op.drop_index("ix_athletes_status", table_name="athletes")
    op.drop_index("ix_athletes_email", table_name="athletes")
    op.drop_table("athletes")

    for enum_name in (
        "goal_status",
        "goal_category",
        "relationship_status",
        "relationship_role",
        "athlete_status",
        "throw_side",
        "bat_side",
        "position",
    ):
        postgresql.ENUM(name=enum_name).drop(op.get_bind(), checkfirst=True)
