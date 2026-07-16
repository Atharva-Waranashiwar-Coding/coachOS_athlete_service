"""Explicit Auth Service user to Athlete Service profile link."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Index, String, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.models.enums import AthleteUserLinkStatus


class AthleteUserLink(Base):
    __tablename__ = "athlete_user_links"
    __table_args__ = (
        Index("ix_athlete_user_links_athlete_id", "athlete_id"),
        Index("ix_athlete_user_links_auth_user_id", "auth_user_id"),
        Index("ix_athlete_user_links_status", "status"),
        Index(
            "uq_athlete_user_links_current_athlete",
            "athlete_id",
            unique=True,
            postgresql_where=text("status IN ('invited', 'active')"),
            sqlite_where=text("status IN ('invited', 'active')"),
        ),
        Index(
            "uq_athlete_user_links_current_auth_user",
            "auth_user_id",
            unique=True,
            postgresql_where=text("status IN ('invited', 'active')"),
            sqlite_where=text("status IN ('invited', 'active')"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    athlete_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("athletes.id", ondelete="CASCADE"),
        nullable=False,
    )
    auth_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    invitation_email: Mapped[str] = mapped_column(String(320), nullable=False)
    status: Mapped[AthleteUserLinkStatus] = mapped_column(
        Enum(
            AthleteUserLinkStatus,
            name="athlete_user_link_status",
            values_callable=lambda values: [item.value for item in values],
        ),
        default=AthleteUserLinkStatus.INVITED,
        nullable=False,
    )
    invited_by_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    invited_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    disabled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )
