"""Persistence operations for explicit athlete identity links."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.athlete_user_link import AthleteUserLink
from app.models.enums import AthleteUserLinkStatus


class AthleteUserLinkRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def add(self, link: AthleteUserLink) -> AthleteUserLink:
        self.db.add(link)
        return link

    def by_athlete(self, athlete_id: UUID, current_only: bool = False) -> AthleteUserLink | None:
        statement = select(AthleteUserLink).where(AthleteUserLink.athlete_id == athlete_id)
        if current_only:
            statement = statement.where(
                AthleteUserLink.status.in_([AthleteUserLinkStatus.INVITED, AthleteUserLinkStatus.ACTIVE])
            )
        return self.db.scalar(statement.order_by(AthleteUserLink.created_at.desc()))

    def by_auth_user(self, auth_user_id: UUID, active_only: bool = False) -> AthleteUserLink | None:
        statement = select(AthleteUserLink).where(AthleteUserLink.auth_user_id == auth_user_id)
        if active_only:
            statement = statement.where(AthleteUserLink.status == AthleteUserLinkStatus.ACTIVE)
        return self.db.scalar(statement.order_by(AthleteUserLink.created_at.desc()))
