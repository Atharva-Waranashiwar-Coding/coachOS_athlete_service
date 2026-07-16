"""Rename the position enum to avoid a PostgreSQL keyword conflict.

Revision ID: 20260716_0006
Revises: 20260716_0005
Create Date: 2026-07-16
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260716_0006"
down_revision: str | None = "20260716_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Rename enum types created by older revisions, if present."""
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM pg_type AS type
                JOIN pg_namespace AS namespace ON namespace.oid = type.typnamespace
                WHERE type.typname = 'position'
                  AND namespace.nspname = current_schema()
            ) AND NOT EXISTS (
                SELECT 1
                FROM pg_type AS type
                JOIN pg_namespace AS namespace ON namespace.oid = type.typnamespace
                WHERE type.typname = 'athlete_position'
                  AND namespace.nspname = current_schema()
            ) THEN
                ALTER TYPE "position" RENAME TO athlete_position;
            END IF;
        END
        $$;
        """
    )


def downgrade() -> None:
    """Restore the legacy enum name when it does not already exist."""
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM pg_type AS type
                JOIN pg_namespace AS namespace ON namespace.oid = type.typnamespace
                WHERE type.typname = 'athlete_position'
                  AND namespace.nspname = current_schema()
            ) AND NOT EXISTS (
                SELECT 1
                FROM pg_type AS type
                JOIN pg_namespace AS namespace ON namespace.oid = type.typnamespace
                WHERE type.typname = 'position'
                  AND namespace.nspname = current_schema()
            ) THEN
                ALTER TYPE athlete_position RENAME TO "position";
            END IF;
        END
        $$;
        """
    )
