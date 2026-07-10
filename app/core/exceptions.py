"""Domain exceptions and centralized exception handlers."""

import logging

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

logger = logging.getLogger(__name__)


class AppError(Exception):
    """Base error class for known application failures."""

    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    code = "internal_error"
    message = "An unexpected error occurred."

    def __init__(self, message: str | None = None) -> None:
        self.message = message or self.message
        super().__init__(self.message)


class BadRequestError(AppError):
    """Raised for invalid domain operations."""

    status_code = status.HTTP_400_BAD_REQUEST
    code = "bad_request"
    message = "Invalid request."


class UnauthorizedError(AppError):
    """Raised for missing, expired, or invalid authentication."""

    status_code = status.HTTP_401_UNAUTHORIZED
    code = "unauthorized"
    message = "Authentication is required."


class ForbiddenError(AppError):
    """Raised when an authenticated user lacks permission."""

    status_code = status.HTTP_403_FORBIDDEN
    code = "forbidden"
    message = "You do not have permission to perform this action."


class NotFoundError(AppError):
    """Raised when a resource is missing or intentionally hidden."""

    status_code = status.HTTP_404_NOT_FOUND
    code = "not_found"
    message = "Resource not found."


class ConflictError(AppError):
    """Raised when a request conflicts with existing state."""

    status_code = status.HTTP_409_CONFLICT
    code = "conflict"
    message = "Resource conflict."


def error_response(status_code: int, code: str, message: str, details: dict | None = None) -> JSONResponse:
    """Build the service-wide error envelope."""
    return JSONResponse(
        status_code=status_code,
        content={"error": {"code": code, "message": message, "details": details or {}}},
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Register centralized error handlers."""

    @app.exception_handler(AppError)
    async def app_error_handler(_: Request, exc: AppError) -> JSONResponse:
        return error_response(exc.status_code, exc.code, exc.message)

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
        errors = [
            {
                "loc": error.get("loc", []),
                "msg": error.get("msg", "Invalid value."),
                "type": error.get("type", "value_error"),
            }
            for error in exc.errors()
        ]
        return error_response(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "validation_error",
            "One or more fields are invalid.",
            {"errors": errors},
        )

    @app.exception_handler(IntegrityError)
    async def integrity_error_handler(_: Request, exc: IntegrityError) -> JSONResponse:
        logger.warning("Database integrity error", extra={"error": str(exc.orig)})
        return error_response(status.HTTP_409_CONFLICT, "conflict", "Resource conflict.")

    @app.exception_handler(SQLAlchemyError)
    async def database_error_handler(_: Request, exc: SQLAlchemyError) -> JSONResponse:
        logger.exception("Database error", exc_info=exc)
        return error_response(status.HTTP_500_INTERNAL_SERVER_ERROR, "database_error", "A database error occurred.")

    @app.exception_handler(Exception)
    async def unhandled_error_handler(_: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled error", exc_info=exc)
        return error_response(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "internal_error",
            "An unexpected error occurred.",
        )
