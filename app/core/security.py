"""JWT validation helpers for Auth Service integration."""

from uuid import UUID

import jwt

from app.core.config import settings
from app.core.exceptions import UnauthorizedError
from app.schemas.auth import CurrentUser


class TokenValidator:
    """Validate bearer tokens without coupling to the Auth Service database."""

    def validate_access_token(self, token: str) -> CurrentUser:
        """Decode and validate a JWT access token."""
        try:
            payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        except jwt.PyJWTError as exc:
            raise UnauthorizedError("Invalid or expired access token.") from exc

        subject = payload.get("sub") or payload.get("user_id")
        email = payload.get("email")
        role = payload.get("role")
        if not subject or not email or not role:
            raise UnauthorizedError("Access token is missing required claims.")

        try:
            return CurrentUser(id=UUID(str(subject)), email=email, role=role)
        except ValueError as exc:
            raise UnauthorizedError("Access token contains invalid identity claims.") from exc


token_validator = TokenValidator()
