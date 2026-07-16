"""Add athlete identity links and athlete assignment activity fields."""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20260716_0004"
down_revision = "20260716_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    link_status = postgresql.ENUM("invited", "active", "disabled", name="athlete_user_link_status", create_type=False)
    actor_type = postgresql.ENUM("coach", "athlete", name="assignment_actor_type", create_type=False)
    note_visibility = postgresql.ENUM(
        "coach_only", "athlete_visible", name="activity_note_visibility", create_type=False
    )
    for enum in (link_status, actor_type, note_visibility):
        enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "athlete_user_links",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column(
            "athlete_id",
            sa.UUID(),
            sa.ForeignKey("athletes.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("auth_user_id", sa.UUID(), nullable=False),
        sa.Column("invitation_email", sa.String(320), nullable=False),
        sa.Column("status", link_status, nullable=False, server_default="invited"),
        sa.Column("invited_by_user_id", sa.UUID(), nullable=False),
        sa.Column("invited_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("activated_at", sa.DateTime(timezone=True)),
        sa.Column("disabled_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_athlete_user_links_athlete_id", "athlete_user_links", ["athlete_id"])
    op.create_index("ix_athlete_user_links_auth_user_id", "athlete_user_links", ["auth_user_id"])
    op.create_index("ix_athlete_user_links_status", "athlete_user_links", ["status"])
    op.create_index(
        "uq_athlete_user_links_current_athlete",
        "athlete_user_links",
        ["athlete_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('invited', 'active')"),
    )
    op.create_index(
        "uq_athlete_user_links_current_auth_user",
        "athlete_user_links",
        ["auth_user_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('invited', 'active')"),
    )

    op.add_column(
        "drill_assignment_activities",
        sa.Column("actor_type", actor_type, nullable=False, server_default="coach"),
    )
    op.add_column(
        "drill_assignment_activities",
        sa.Column("note_visibility", note_visibility, nullable=False, server_default="coach_only"),
    )
    op.add_column("drill_assignment_activities", sa.Column("actual_sets", sa.Integer()))
    op.add_column("drill_assignment_activities", sa.Column("actual_repetitions", sa.Integer()))
    op.add_column("drill_assignment_activities", sa.Column("actual_duration_minutes", sa.Integer()))
    op.alter_column("drill_assignment_activities", "actor_type", server_default=None)
    op.alter_column("drill_assignment_activities", "note_visibility", server_default=None)
    op.alter_column("athlete_user_links", "status", server_default=None)


def downgrade() -> None:
    op.drop_column("drill_assignment_activities", "actual_duration_minutes")
    op.drop_column("drill_assignment_activities", "actual_repetitions")
    op.drop_column("drill_assignment_activities", "actual_sets")
    op.drop_column("drill_assignment_activities", "note_visibility")
    op.drop_column("drill_assignment_activities", "actor_type")
    op.drop_table("athlete_user_links")
    for name in ("activity_note_visibility", "assignment_actor_type", "athlete_user_link_status"):
        postgresql.ENUM(name=name).drop(op.get_bind(), checkfirst=True)
