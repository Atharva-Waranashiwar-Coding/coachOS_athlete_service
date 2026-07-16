"""Authentication and role dependencies."""

from collections.abc import Callable

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.exceptions import ForbiddenError, UnauthorizedError
from app.core.security import token_validator
from app.models.enums import UserRole
from app.schemas.auth import CurrentUser

bearer_scheme = HTTPBearer(auto_error=False)


def get_bearer_token(credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme)) -> str:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise UnauthorizedError("Bearer authentication is required.")
    return credentials.credentials


def get_current_user(token: str = Depends(get_bearer_token)) -> CurrentUser:
    """Validate a bearer token and return the current user."""
    return token_validator.validate_access_token(token)


def require_roles(*roles: UserRole) -> Callable[[CurrentUser], CurrentUser]:
    """Return a dependency that permits only the provided user roles."""

    def role_checker(current_user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if current_user.role not in roles:
            raise ForbiddenError("This endpoint requires a different role.")
        return current_user

    return role_checker


def require_coach(current_user: CurrentUser = Depends(require_roles(UserRole.COACH))) -> CurrentUser:
    """Require an authenticated coach user."""
    return current_user


def require_athlete(current_user: CurrentUser = Depends(require_roles(UserRole.ATHLETE))) -> CurrentUser:
    """Require an authenticated athlete user."""
    return current_user
