"""Typed application settings.

Everything is environment-driven. There are no secrets in this file and no default
that would be unsafe in production: the app refuses to boot with a development
``SECRET_KEY`` when ``ENVIRONMENT=production``.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Annotated, Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

#: Refused at startup when ENVIRONMENT=production (see _production_guards).
DEV_SECRET = "dev-only-secret-change-me"  # noqa: S105


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", ".env.local"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # -- core ---------------------------------------------------------------
    environment: Literal["development", "test", "staging", "production"] = "development"
    app_name: str = "JobApply"
    api_v1_prefix: str = "/api/v1"
    debug: bool = False
    secret_key: str = DEV_SECRET

    # -- datastores ---------------------------------------------------------
    database_url: str = "postgresql+psycopg://jobapply:jobapply@localhost:5432/jobapply"
    database_pool_size: int = 10
    database_max_overflow: int = 20
    redis_url: str = "redis://localhost:6379/0"

    # -- auth ---------------------------------------------------------------
    access_token_ttl_seconds: int = 60 * 15
    refresh_token_ttl_seconds: int = 60 * 60 * 24 * 30
    email_verification_ttl_seconds: int = 60 * 60 * 24
    password_reset_ttl_seconds: int = 60 * 60
    cookie_domain: str | None = None
    cookie_secure: bool = False
    access_cookie_name: str = "ja_access"
    refresh_cookie_name: str = "ja_refresh"
    csrf_cookie_name: str = "ja_csrf"
    csrf_header_name: str = "X-CSRF-Token"

    google_client_id: str | None = None
    google_client_secret: str | None = None
    google_redirect_uri: str = "http://localhost:8000/api/v1/auth/oauth/google/callback"

    # -- frontend -----------------------------------------------------------
    frontend_base_url: str = "http://localhost:3000"
    # NoDecode keeps pydantic-settings from JSON-parsing the raw value, so the
    # comma-separated form used in .env reaches the validator below intact.
    cors_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["http://localhost:3000"]
    )

    # -- storage ------------------------------------------------------------
    storage_backend: Literal["local", "s3"] = "local"
    storage_local_root: str = "./.storage"
    aws_access_key_id: str | None = None
    aws_secret_access_key: str | None = None
    aws_region: str = "us-east-1"
    aws_s3_bucket: str | None = None
    aws_s3_endpoint_url: str | None = None
    upload_max_bytes: int = 10 * 1024 * 1024

    # -- e-mail -------------------------------------------------------------
    email_backend: Literal["console", "smtp"] = "console"
    email_from: str = "no-reply@jobapply.local"
    smtp_host: str = "localhost"
    smtp_port: int = 1025
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_use_tls: bool = False

    # -- ai -----------------------------------------------------------------
    ai_provider: Literal["mock", "openai", "anthropic"] = "mock"
    openai_api_key: str | None = None
    openai_model: str = "gpt-4.1"
    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-sonnet-5"
    ai_timeout_seconds: int = 60
    ai_max_output_tokens: int = 4096

    # -- automation ---------------------------------------------------------
    automation_daily_limit: int = 25
    automation_hourly_limit: int = 5
    automation_min_delay_seconds: int = 45
    automation_max_delay_seconds: int = 180
    automation_min_match_score: int = 70
    confidence_auto_threshold: float = 0.95
    confidence_review_threshold: float = 0.80
    browser_headless: bool = True
    #: Pin a specific Chromium build. Useful in images where Playwright's expected
    #: revision differs from the one installed.
    browser_executable_path: str | None = None
    browser_session_ttl_seconds: int = 60 * 30

    # -- billing ------------------------------------------------------------
    billing_backend: Literal["noop", "stripe"] = "noop"
    stripe_secret_key: str | None = None
    stripe_webhook_secret: str | None = None

    # -- observability ------------------------------------------------------
    log_level: str = "INFO"
    log_format: Literal["json", "console"] = "json"
    sentry_dsn: str | None = None
    otel_exporter_otlp_endpoint: str | None = None

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> object:
        """Accept both the comma-separated form used in .env files and a JSON array."""
        if not isinstance(value, str):
            return value
        text = value.strip()
        if text.startswith("["):
            import json

            try:
                return json.loads(text)
            except json.JSONDecodeError as exc:
                raise ValueError("CORS_ORIGINS looked like JSON but could not be parsed") from exc
        return [item.strip() for item in text.split(",") if item.strip()]

    @model_validator(mode="after")
    def _production_guards(self) -> Settings:
        if self.environment == "production":
            if self.secret_key == DEV_SECRET or len(self.secret_key) < 32:
                raise ValueError("SECRET_KEY must be a strong, non-default value in production")
            if not self.cookie_secure:
                raise ValueError("COOKIE_SECURE must be true in production")
        return self

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()
