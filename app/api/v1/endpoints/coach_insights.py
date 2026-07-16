"""Coach-wide insight overview and attention queue endpoints."""

from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.insight_rules import InsightRange, resolve_insight_period
from app.db.session import get_db
from app.dependencies.auth import require_coach
from app.models.enums import AthleteStatus, Position
from app.schemas.auth import CurrentUser
from app.schemas.insights import CoachAttentionPage, CoachInsightsResponse
from app.services.insights.progress_insight_service import ProgressInsightService

router = APIRouter(prefix="/coach/insights", tags=["insights"])


def period_dependency(
    range_code: InsightRange = Query(default="30d", alias="range"),
    start_date: date | None = None,
    end_date: date | None = None,
    compare: bool = True,
    timezone: str = "UTC",
):
    return resolve_insight_period(
        range_code,
        start_date=start_date,
        end_date=end_date,
        compare=compare,
        timezone=timezone,
    )


@router.get("", response_model=CoachInsightsResponse)
def coach_insights(
    status: AthleteStatus | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=5, ge=1, le=settings.max_page_size),
    period=Depends(period_dependency),
    user: CurrentUser = Depends(require_coach),
    db: Session = Depends(get_db),
) -> CoachInsightsResponse:
    return ProgressInsightService(db).coach(user.id, period, status, page, page_size)


@router.get("/athletes-needing-attention", response_model=CoachAttentionPage)
def athletes_needing_attention(
    severity: str | None = Query(default=None, pattern="^(info|warning|high)$"),
    flag_code: str | None = None,
    primary_position: Position | None = None,
    search: str | None = Query(default=None, max_length=100),
    sort_by: str = Query(
        default="highest_severity",
        pattern="^(highest_severity|overdue_count|last_activity|name)$",
    ),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=settings.default_page_size, ge=1, le=settings.max_page_size),
    period=Depends(period_dependency),
    user: CurrentUser = Depends(require_coach),
    db: Session = Depends(get_db),
) -> CoachAttentionPage:
    return ProgressInsightService(db).attention_page(
        user.id,
        period,
        severity=severity,
        flag_code=flag_code,
        primary_position=primary_position.value if primary_position else None,
        search=search,
        sort_by=sort_by,
        page=page,
        page_size=page_size,
    )
