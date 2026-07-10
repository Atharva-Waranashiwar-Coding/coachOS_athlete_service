"""upgrade unified timeline

Revision ID: 20260710_0002
Revises: 20260710_0001
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20260710_0002"
down_revision = "20260710_0001"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    category = postgresql.ENUM(
        "profile",
        "goal",
        "practice",
        "video",
        "ai_review",
        "coach_review",
        "drill",
        "system",
        name="timeline_event_category",
    )
    visibility = postgresql.ENUM("coach_only", "athlete_visible", name="timeline_visibility")
    category.create(bind, checkfirst=True)
    visibility.create(bind, checkfirst=True)
    op.add_column("timeline_events", sa.Column("external_event_id", sa.UUID()))
    op.add_column("timeline_events", sa.Column("event_category", category))
    op.add_column("timeline_events", sa.Column("actor_user_id", sa.UUID()))
    op.add_column("timeline_events", sa.Column("schema_version", sa.Integer(), server_default="1"))
    op.add_column("timeline_events", sa.Column("visibility", visibility))
    op.execute("UPDATE timeline_events SET actor_user_id = created_by_user_id")
    op.execute(
        "UPDATE timeline_events SET event_category = CASE WHEN event_type LIKE 'goal_%' THEN 'goal'::timeline_event_category WHEN event_type LIKE 'athlete_%' OR event_type LIKE 'injury_note_%' THEN 'profile'::timeline_event_category ELSE 'system'::timeline_event_category END"
    )
    op.execute(
        "UPDATE timeline_events SET visibility = CASE WHEN event_type LIKE 'injury_note_%' THEN 'coach_only'::timeline_visibility ELSE 'athlete_visible'::timeline_visibility END"
    )
    op.alter_column("timeline_events", "event_category", nullable=False)
    op.alter_column("timeline_events", "visibility", nullable=False)
    op.alter_column("timeline_events", "schema_version", nullable=False)
    op.drop_column("timeline_events", "created_by_user_id")
    op.drop_index("ix_timeline_athlete_occurred_at", table_name="timeline_events")
    op.create_index(
        "ix_timeline_athlete_occurred_created",
        "timeline_events",
        ["athlete_id", sa.text("occurred_at DESC"), sa.text("created_at DESC")],
    )
    op.create_index("ix_timeline_athlete_category", "timeline_events", ["athlete_id", "event_category"])
    op.create_index("ix_timeline_athlete_event_type", "timeline_events", ["athlete_id", "event_type"])
    op.create_index("ix_timeline_events_source_service", "timeline_events", ["source_service"])
    op.create_index("ix_timeline_source_entity", "timeline_events", ["source_entity_type", "source_entity_id"])
    op.create_index("ix_timeline_events_visibility", "timeline_events", ["visibility"])
    op.create_index(
        "ix_timeline_external_event_id",
        "timeline_events",
        ["external_event_id"],
        unique=True,
        postgresql_where=sa.text("external_event_id IS NOT NULL"),
    )
    op.create_check_constraint("ck_timeline_schema_version_positive", "timeline_events", "schema_version > 0")
    op.create_check_constraint("ck_timeline_title_nonempty", "timeline_events", "length(trim(title)) > 0")
    op.create_check_constraint(
        "ck_timeline_source_service_nonempty", "timeline_events", "length(trim(source_service)) > 0"
    )
    op.create_check_constraint("ck_timeline_event_type_nonempty", "timeline_events", "length(trim(event_type)) > 0")


def downgrade():
    for name in (
        "ck_timeline_event_type_nonempty",
        "ck_timeline_source_service_nonempty",
        "ck_timeline_title_nonempty",
        "ck_timeline_schema_version_positive",
    ):
        op.drop_constraint(name, "timeline_events", type_="check")
    for name in (
        "ix_timeline_external_event_id",
        "ix_timeline_events_visibility",
        "ix_timeline_source_entity",
        "ix_timeline_events_source_service",
        "ix_timeline_athlete_event_type",
        "ix_timeline_athlete_category",
        "ix_timeline_athlete_occurred_created",
    ):
        op.drop_index(name, table_name="timeline_events")
    op.add_column("timeline_events", sa.Column("created_by_user_id", sa.UUID()))
    op.execute("UPDATE timeline_events SET created_by_user_id = actor_user_id")
    for column in ("visibility", "schema_version", "actor_user_id", "event_category", "external_event_id"):
        op.drop_column("timeline_events", column)
    op.create_index("ix_timeline_athlete_occurred_at", "timeline_events", ["athlete_id", "occurred_at"])
    postgresql.ENUM(name="timeline_visibility").drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(name="timeline_event_category").drop(op.get_bind(), checkfirst=True)
