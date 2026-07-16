"""SQLAlchemy metadata imports for migrations."""

from app.db.session import Base
from app.models.athlete import Athlete, AthleteSecondaryPosition, CoachAthleteRelationship
from app.models.athlete_user_link import AthleteUserLink
from app.models.drill import Drill
from app.models.drill_assignment import DrillAssignment
from app.models.drill_assignment_activity import DrillAssignmentActivity
from app.models.goal import AthleteGoal
from app.models.timeline import TimelineEvent

__all__ = [
    "Athlete",
    "AthleteGoal",
    "AthleteUserLink",
    "Drill",
    "DrillAssignment",
    "DrillAssignmentActivity",
    "AthleteSecondaryPosition",
    "Base",
    "CoachAthleteRelationship",
    "TimelineEvent",
]
