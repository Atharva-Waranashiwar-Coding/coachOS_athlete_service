"""Coach-authorized athlete progress insight endpoint."""

from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.insight_rules import InsightRange, resolve_insight_period
from app.db.session import get_db
from app.dependencies.athlete_access import get_accessible_athlete
from app.dependencies.auth import require_coach
from app.models.athlete import Athlete
from app.schemas.auth import CurrentUser
from app.schemas.insights import AthleteProgressInsights
from app.services.insights.progress_insight_service import ALL_SECTIONS, ProgressInsightService

router = APIRouter(prefix="/athletes/{athlete_id}/insights", tags=["insights"])


@router.get("", response_model=AthleteProgressInsights)
def athlete_insights(
    range_code: InsightRange = Query(default="30d", alias="range"),
    start_date: date | None = None,
    end_date: date | None = None,
    compare: bool = True,
    timezone: str = "UTC",
    sections: str | None = None,
    athlete: Athlete = Depends(get_accessible_athlete),
    user: CurrentUser = Depends(require_coach),
    db: Session = Depends(get_db),
) -> AthleteProgressInsights:
    selected = {item.strip() for item in sections.split(",") if item.strip()} if sections else None
    if selected and not selected.issubset(ALL_SECTIONS):
        from app.core.exceptions import BadRequestError

        raise BadRequestError("sections contains an unsupported insight section.")
    period = resolve_insight_period(
        range_code,
        start_date=start_date,
        end_date=end_date,
        compare=compare,
        timezone=timezone,
    )
    return ProgressInsightService(db).athlete(athlete, user.id, period, selected)
