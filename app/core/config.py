"""Application configuration for the Athlete Service."""

import json
from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings loaded from environment variables."""

    app_name: str = Field(default="coachos-athlete-service", alias="APP_NAME")
    app_env: str = Field(default="development", alias="APP_ENV")
    api_v1_prefix: str = Field(default="/api/v1", alias="API_V1_PREFIX")
    database_url: str = Field(alias="DATABASE_URL")
    jwt_secret_key: str = Field(alias="JWT_SECRET_KEY")
    jwt_algorithm: str = Field(default="HS256", alias="JWT_ALGORITHM")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    cors_origins: list[str] = Field(default_factory=list, alias="CORS_ORIGINS")
    default_page_size: int = Field(default=20, alias="DEFAULT_PAGE_SIZE", gt=0)
    max_page_size: int = Field(default=100, alias="MAX_PAGE_SIZE", gt=0, le=500)
    graduation_year_min: int = Field(default=2020, alias="GRADUATION_YEAR_MIN")
    graduation_year_max: int = Field(default=2045, alias="GRADUATION_YEAR_MAX")
    internal_api_prefix: str = Field(default="/internal/v1", alias="INTERNAL_API_PREFIX")
    internal_service_tokens: dict[str, str] = Field(default_factory=dict, alias="INTERNAL_SERVICE_TOKENS")
    ai_review_service_url: str = Field(default="http://localhost:8004", alias="AI_REVIEW_SERVICE_URL")
    upstream_timeout_seconds: float = Field(default=5, alias="UPSTREAM_TIMEOUT_SECONDS", gt=0)
    max_drill_title_characters: int = Field(default=200, alias="MAX_DRILL_TITLE_CHARACTERS")
    max_drill_description_characters: int = Field(default=5000, alias="MAX_DRILL_DESCRIPTION_CHARACTERS")
    max_drill_instructions_characters: int = Field(default=10000, alias="MAX_DRILL_INSTRUCTIONS_CHARACTERS")
    max_coach_notes_characters: int = Field(default=10000, alias="MAX_COACH_NOTES_CHARACTERS")
    max_drill_tags: int = Field(default=30, alias="MAX_DRILL_TAGS")
    max_drill_equipment_items: int = Field(default=30, alias="MAX_DRILL_EQUIPMENT_ITEMS")
    default_drill_assignment_page_size: int = Field(default=20, alias="DEFAULT_DRILL_ASSIGNMENT_PAGE_SIZE", gt=0)
    auth_service_internal_url: str = Field(default="http://localhost:8001", alias="AUTH_SERVICE_INTERNAL_URL")
    internal_service_name: str = Field(default="athlete-service", alias="INTERNAL_SERVICE_NAME")
    internal_service_token: str = Field(default="", alias="INTERNAL_SERVICE_TOKEN")
    athlete_dashboard_recent_items_limit: int = Field(
        default=5, alias="ATHLETE_DASHBOARD_RECENT_ITEMS_LIMIT", gt=0, le=20
    )
    athlete_account_link_required: bool = Field(default=True, alias="ATHLETE_ACCOUNT_LINK_REQUIRED")
    max_athlete_note_characters: int = Field(default=3000, alias="MAX_ATHLETE_NOTE_CHARACTERS", gt=0)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: str | list[str]) -> list[str]:
        """Parse comma-separated CORS origins from environment variables."""
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @field_validator("internal_service_tokens", mode="before")
    @classmethod
    def parse_internal_tokens(cls, value: str | dict[str, str]) -> dict[str, str]:
        if isinstance(value, str):
            parsed = json.loads(value)
            if not isinstance(parsed, dict) or not all(
                isinstance(k, str) and isinstance(v, str) for k, v in parsed.items()
            ):
                raise ValueError("INTERNAL_SERVICE_TOKENS must be a JSON object of string values")
            return parsed
        return value


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings."""
    return Settings()  # type: ignore[call-arg]


settings = get_settings()
