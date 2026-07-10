"""SQLAlchemy metadata imports for migrations."""

from app.db.session import Base
from app.models.athlete import Athlete, AthleteSecondaryPosition, CoachAthleteRelationship
from app.models.goal import AthleteGoal
from app.models.timeline import TimelineEvent

__all__ = [
    "Athlete",
    "AthleteGoal",
    "AthleteSecondaryPosition",
    "Base",
    "CoachAthleteRelationship",
    "TimelineEvent",
]
