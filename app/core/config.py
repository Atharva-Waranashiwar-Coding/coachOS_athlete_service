"""Application configuration for the Athlete Service."""

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


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings."""
    return Settings()


settings = get_settings()
