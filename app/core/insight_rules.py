"""Date-range and configurable deterministic insight rules."""

from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.core.config import settings
from app.core.exceptions import BadRequestError

InsightRange = Literal["7d", "30d", "60d", "90d", "custom"]


def as_utc(value: datetime) -> datetime:
    """Normalize PostgreSQL or SQLite timestamps to aware UTC."""
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


@dataclass(frozen=True)
class InsightPeriod:
    range_code: InsightRange
    timezone: str
    start: datetime
    end: datetime
    previous_start: datetime | None
    previous_end: datetime | None
    end_local_date: date


def resolve_insight_period(
    range_code: InsightRange = "30d",
    *,
    start_date: date | None = None,
    end_date: date | None = None,
    compare: bool = True,
    timezone: str = "UTC",
    now: datetime | None = None,
) -> InsightPeriod:
    """Resolve start-inclusive, end-exclusive UTC boundaries."""
    try:
        zone = ZoneInfo(timezone)
    except ZoneInfoNotFoundError as exc:
        raise BadRequestError("timezone must be a valid IANA timezone.") from exc
    current = (now or datetime.now(UTC)).astimezone(zone)
    if range_code == "custom":
        if start_date is None or end_date is None:
            raise BadRequestError("start_date and end_date are required for a custom range.")
        if end_date < start_date:
            raise BadRequestError("end_date must be on or after start_date.")
        local_start = datetime.combine(start_date, time.min, tzinfo=zone)
        local_end = datetime.combine(end_date + timedelta(days=1), time.min, tzinfo=zone)
    else:
        days = int(range_code.removesuffix("d"))
        local_end = datetime.combine(current.date() + timedelta(days=1), time.min, tzinfo=zone)
        local_start = local_end - timedelta(days=days)
    duration = local_end - local_start
    if duration > timedelta(days=settings.insight_max_range_days):
        raise BadRequestError("Requested insight range exceeds the configured maximum.")
    previous_start = local_start - duration if compare else None
    previous_end = local_start if compare else None
    return InsightPeriod(
        range_code=range_code,
        timezone=timezone,
        start=local_start.astimezone(UTC),
        end=local_end.astimezone(UTC),
        previous_start=previous_start.astimezone(UTC) if previous_start else None,
        previous_end=previous_end.astimezone(UTC) if previous_end else None,
        end_local_date=local_end.date(),
    )
