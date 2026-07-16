"""Trusted Auth Service client for athlete invitation provisioning."""

from uuid import UUID

import httpx
from pydantic import BaseModel, EmailStr, ValidationError

from app.core.config import settings
from app.core.exceptions import ConflictError, UpstreamServiceError


class AuthAthleteUserResponse(BaseModel):
    auth_user_id: UUID
    user_status: str
    invitation_id: UUID | None
    development_invitation_url: str | None = None


class AuthServiceClient:
    def __init__(self, client: httpx.Client | None = None) -> None:
        self.client = client or httpx.Client(timeout=settings.upstream_timeout_seconds)

    def create_athlete_user(
        self, email: EmailStr, athlete_id: UUID, invited_by_user_id: UUID
    ) -> AuthAthleteUserResponse:
        return self._request(
            "POST",
            "/internal/v1/athlete-users",
            {"email": str(email), "athlete_id": str(athlete_id), "invited_by_user_id": str(invited_by_user_id)},
        )

    def resend(
        self, auth_user_id: UUID, email: EmailStr, athlete_id: UUID, invited_by_user_id: UUID
    ) -> AuthAthleteUserResponse:
        return self._request(
            "POST",
            f"/internal/v1/athlete-users/{auth_user_id}/resend",
            {"email": str(email), "athlete_id": str(athlete_id), "invited_by_user_id": str(invited_by_user_id)},
        )

    def disable(self, auth_user_id: UUID) -> None:
        try:
            response = self.client.post(
                f"{settings.auth_service_internal_url.rstrip('/')}/internal/v1/athlete-users/{auth_user_id}/disable",
                headers={
                    "X-Service-Name": settings.internal_service_name,
                    "X-Service-Token": settings.internal_service_token,
                },
            )
        except httpx.HTTPError as exc:
            raise UpstreamServiceError("Auth Service is unavailable.") from exc
        if response.status_code >= 400:
            raise UpstreamServiceError("Auth Service could not disable the athlete account.")

    def _request(
        self,
        method: str,
        path: str,
        json: dict[str, str] | None,
    ) -> AuthAthleteUserResponse:
        try:
            response = self.client.request(
                method,
                f"{settings.auth_service_internal_url.rstrip('/')}{path}",
                json=json,
                headers={
                    "X-Service-Name": settings.internal_service_name,
                    "X-Service-Token": settings.internal_service_token,
                },
            )
        except httpx.HTTPError as exc:
            raise UpstreamServiceError("Auth Service is unavailable.") from exc
        if response.status_code == 409:
            raise ConflictError("Athlete account invitation conflicts with existing identity.")
        if response.status_code >= 400:
            raise UpstreamServiceError("Auth Service could not process the athlete account.")
        try:
            return AuthAthleteUserResponse.model_validate(response.json())
        except ValidationError as exc:
            raise UpstreamServiceError("Auth Service returned an invalid invitation contract.") from exc
