"""Athlete and coach-athlete relationship ORM models."""

import uuid
from datetime import UTC, date, datetime

from sqlalchemy import Date, DateTime, Enum, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.enums import (
    AthleteStatus,
    BatSide,
    Position,
    RelationshipRole,
    RelationshipStatus,
    ThrowSide,
)


class Athlete(Base):
    """Athlete profile owned by the Athlete Service."""

    __tablename__ = "athletes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    preferred_name: Mapped[str | None] = mapped_column(String(100))
    date_of_birth: Mapped[date | None] = mapped_column(Date)
    email: Mapped[str | None] = mapped_column(String(320), index=True)
    phone: Mapped[str | None] = mapped_column(String(50))
    primary_position: Mapped[Position | None] = mapped_column(
        Enum(Position, name="position", values_callable=lambda values: [item.value for item in values])
    )
    bats: Mapped[BatSide | None] = mapped_column(
        Enum(BatSide, name="bat_side", values_callable=lambda values: [item.value for item in values])
    )
    throws: Mapped[ThrowSide | None] = mapped_column(
        Enum(ThrowSide, name="throw_side", values_callable=lambda values: [item.value for item in values])
    )
    graduation_year: Mapped[int | None] = mapped_column(Integer)
    school_name: Mapped[str | None] = mapped_column(String(200))
    team_name: Mapped[str | None] = mapped_column(String(200))
    height_inches: Mapped[int | None] = mapped_column(Integer)
    weight_pounds: Mapped[int | None] = mapped_column(Integer)
    injury_notes: Mapped[str | None] = mapped_column(Text)
    general_notes: Mapped[str | None] = mapped_column(Text)
    status: Mapped[AthleteStatus] = mapped_column(
        Enum(AthleteStatus, name="athlete_status", values_callable=lambda values: [item.value for item in values]),
        default=AthleteStatus.ACTIVE,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    secondary_position_rows: Mapped[list["AthleteSecondaryPosition"]] = relationship(
        back_populates="athlete",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    relationships: Mapped[list["CoachAthleteRelationship"]] = relationship(
        back_populates="athlete",
        cascade="all, delete-orphan",
    )

    @property
    def secondary_positions(self) -> list[Position]:
        """Return secondary position enum values for response serialization."""
        return [row.position for row in self.secondary_position_rows]


class AthleteSecondaryPosition(Base):
    """Normalized secondary athlete positions for validation and querying."""

    __tablename__ = "athlete_secondary_positions"

    athlete_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("athletes.id", ondelete="CASCADE"),
        primary_key=True,
    )
    position: Mapped[Position] = mapped_column(
        Enum(Position, name="position", values_callable=lambda values: [item.value for item in values]),
        primary_key=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )

    athlete: Mapped[Athlete] = relationship(back_populates="secondary_position_rows")


class CoachAthleteRelationship(Base):
    """Relationship between an external Auth Service coach user and an athlete."""

    __tablename__ = "coach_athlete_relationships"
    __table_args__ = (
        UniqueConstraint("coach_user_id", "athlete_id", name="uq_coach_athlete_relationship"),
        Index("ix_relationships_coach_user_id", "coach_user_id"),
        Index("ix_relationships_athlete_id", "athlete_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    coach_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    athlete_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("athletes.id", ondelete="CASCADE"),
        nullable=False,
    )
    relationship_role: Mapped[RelationshipRole] = mapped_column(
        Enum(RelationshipRole, name="relationship_role", values_callable=lambda values: [item.value for item in values]),
        nullable=False,
    )
    status: Mapped[RelationshipStatus] = mapped_column(
        Enum(RelationshipStatus, name="relationship_status", values_callable=lambda values: [item.value for item in values]),
        default=RelationshipStatus.ACTIVE,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    athlete: Mapped[Athlete] = relationship(back_populates="relationships")


Index("ix_athletes_status", Athlete.status)
Index("ix_athletes_name", Athlete.last_name, Athlete.first_name)
Index("ix_athletes_graduation_year", Athlete.graduation_year)
Index("ix_athletes_primary_position", Athlete.primary_position)
