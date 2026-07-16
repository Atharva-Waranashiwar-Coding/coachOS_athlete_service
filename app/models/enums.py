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


class EventCategory(str, enum.Enum):
    PROFILE = "profile"
    GOAL = "goal"
    PRACTICE = "practice"
    VIDEO = "video"
    AI_REVIEW = "ai_review"
    COACH_REVIEW = "coach_review"
    DRILL = "drill"
    SYSTEM = "system"


class TimelineVisibility(str, enum.Enum):
    COACH_ONLY = "coach_only"
    ATHLETE_VISIBLE = "athlete_visible"


class DrillCategory(str, enum.Enum):
    HITTING = "hitting"
    PITCHING = "pitching"
    FIELDING = "fielding"
    THROWING = "throwing"
    CATCHING = "catching"
    FOOTWORK = "footwork"
    SPEED = "speed"
    STRENGTH = "strength"
    MOBILITY = "mobility"
    CONDITIONING = "conditioning"
    RECOVERY = "recovery"
    MENTAL = "mental"
    GENERAL = "general"


class DrillDifficulty(str, enum.Enum):
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"


class DrillVisibility(str, enum.Enum):
    PRIVATE = "private"
    ORGANIZATION = "organization"
    SYSTEM = "system"


class DrillStatus(str, enum.Enum):
    ACTIVE = "active"
    ARCHIVED = "archived"


class DrillAssignmentStatus(str, enum.Enum):
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class DrillActivityType(str, enum.Enum):
    ASSIGNED = "assigned"
    STARTED = "started"
    UPDATED = "updated"
    PROGRESS_UPDATED = "progress_updated"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class AthleteUserLinkStatus(str, enum.Enum):
    INVITED = "invited"
    ACTIVE = "active"
    DISABLED = "disabled"


class AssignmentActorType(str, enum.Enum):
    COACH = "coach"
    ATHLETE = "athlete"


class ActivityNoteVisibility(str, enum.Enum):
    COACH_ONLY = "coach_only"
    ATHLETE_VISIBLE = "athlete_visible"
