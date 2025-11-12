"""app.config
=================
Mini-README: Centralises configuration management using Pydantic settings. The module
defines strongly typed settings for server, security, and external service access.
Usage: import `get_settings()` to retrieve a cached configuration instance.
"""

from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application configuration container leveraging environment variables."""

    app_name: str = Field(default="Nichifier Business Intelligence Platform")
    environment: str = Field(default="development")
    secret_key: str = Field(default="change-me-secret-key")
    token_expiry_minutes: int = Field(default=60)
    database_url: str = Field(default="sqlite+aiosqlite:///./nichifier.db")
    database_echo: bool = Field(default=False)
    default_host: str = Field(default="127.0.0.1")
    default_port: int = Field(default=8000)
    openai_api_key: str | None = Field(default=None)
    newsletter_daily_hour: int = Field(default=6)
    newsletter_weekly_day: int = Field(default=1)
    newsletter_monthly_day: int = Field(default=1)
    newsletter_quarterly_month: int = Field(default=1)

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache
def get_settings() -> Settings:
    """Return a cached instance of application settings."""

    return Settings()
