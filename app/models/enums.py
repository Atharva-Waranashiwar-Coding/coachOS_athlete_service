"""Domain enum definitions for the Athlete Service."""

import enum


class UserRole(str, enum.Enum):
    """Roles issued by the Auth Service."""

    COACH = "coach"
    ATHLETE = "athlete"
    ADMIN = "admin"


class Position(str, enum.Enum):
    """Baseball or softball position values."""

    PITCHER = "pitcher"
    CATCHER = "catcher"
    FIRST_BASE = "first_base"
    SECOND_BASE = "second_base"
    THIRD_BASE = "third_base"
    SHORTSTOP = "shortstop"
    LEFT_FIELD = "left_field"
    CENTER_FIELD = "center_field"
    RIGHT_FIELD = "right_field"
    UTILITY = "utility"


class BatSide(str, enum.Enum):
    """Batting side."""

    LEFT = "left"
    RIGHT = "right"
    SWITCH = "switch"


class ThrowSide(str, enum.Enum):
    """Throwing side."""

    LEFT = "left"
    RIGHT = "right"


class AthleteStatus(str, enum.Enum):
    """Athlete lifecycle state."""

    ACTIVE = "active"
    INACTIVE = "inactive"
    ARCHIVED = "archived"


class RelationshipRole(str, enum.Enum):
    """Coach permissions for an athlete."""

    PRIMARY_COACH = "primary_coach"
    ASSISTANT_COACH = "assistant_coach"
    VIEWER = "viewer"


class RelationshipStatus(str, enum.Enum):
    """Coach-athlete relationship state."""

    ACTIVE = "active"
    INACTIVE = "inactive"


class GoalCategory(str, enum.Enum):
    """Goal categories."""

    HITTING = "hitting"
    PITCHING = "pitching"
    FIELDING = "fielding"
    STRENGTH = "strength"
    SPEED = "speed"
    MOBILITY = "mobility"
    MENTAL = "mental"
    RECRUITING = "recruiting"
    GENERAL = "general"


class GoalStatus(str, enum.Enum):
    """Goal lifecycle state."""

    ACTIVE = "active"
    COMPLETED = "completed"
    PAUSED = "paused"
    CANCELLED = "cancelled"


class TimelineEventType(str, enum.Enum):
    """Known timeline event types with room for future expansion."""

    ATHLETE_CREATED = "athlete_created"
    ATHLETE_UPDATED = "athlete_updated"
    ATHLETE_ARCHIVED = "athlete_archived"
    ATHLETE_RESTORED = "athlete_restored"
    INJURY_NOTE_UPDATED = "injury_note_updated"
    GOAL_CREATED = "goal_created"
    GOAL_UPDATED = "goal_updated"
    GOAL_COMPLETED = "goal_completed"
    GOAL_CANCELLED = "goal_cancelled"
