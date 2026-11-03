"""Application settings loaded from environment variables (ARCHITECTURE.md section 6).

Values come from the process environment first, then from an optional ``.env`` file in the
working directory. Empty values are treated as unset so ``.env.example`` can be copied as is.
"""

from __future__ import annotations

import logging
import secrets
from functools import lru_cache
from typing import Annotated, Any, Literal, Self

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

logger = logging.getLogger(__name__)

Environment = Literal["development", "production"]

MIN_JWT_SECRET_LENGTH = 32
MIN_ADMIN_TOKEN_LENGTH = 32
DEFAULT_CORS_ORIGINS = ("http://localhost:8081", "http://localhost:19006")

# SQLAlchemy needs an explicit driver, but hosts (Neon, Render, Heroku-style tools) hand out
# postgres:// or postgresql:// URLs. Those schemes are rewritten to use psycopg 3.
_DRIVERLESS_POSTGRES_SCHEMES = frozenset({"postgres", "postgresql"})
_POSTGRES_DRIVER_SCHEME = "postgresql+psycopg"


class Settings(BaseSettings):
    """Typed view of the backend configuration."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_ignore_empty=True,
        case_sensitive=False,
        extra="ignore",
        # Validation errors must never echo secrets (JWT_SECRET, ADMIN_TOKEN) into logs.
        hide_input_in_errors=True,
    )

    env: Environment = "development"
    database_url: str = "sqlite:///./shopex.db"
    jwt_secret: SecretStr = SecretStr("")
    jwt_expire_minutes: int = Field(default=10080, gt=0)
    cors_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: list(DEFAULT_CORS_ORIGINS)
    )
    admin_token: SecretStr | None = None
    overpass_url: str = "https://overpass-api.de/api/interpreter"
    osrm_url: str = "https://router.project-osrm.org"
    http_timeout_s: float = Field(default=20.0, gt=0)
    # The public Overpass server often needs 20-45 s for a city-sized query.
    overpass_timeout_s: float = Field(default=45.0, gt=0)
    max_radius_km: float = Field(default=50.0, gt=0)
    max_stores_per_area: int = Field(default=60, gt=0)
    price_source: str = "demo"
    # Resolved from ENV when left unset (see _default_demo_stores_fallback).
    demo_stores_fallback: bool = True
    daily_refresh_in_process: bool = False

    @property
    def is_production(self) -> bool:
        return self.env == "production"

    @model_validator(mode="before")
    @classmethod
    def _default_demo_stores_fallback(cls, data: Any) -> Any:
        """DEMO_STORES_FALLBACK defaults to true in development and false in production."""
        if isinstance(data, dict) and data.get("demo_stores_fallback") in (None, ""):
            env = str(data.get("env") or "development").strip().lower()
            data = {**data, "demo_stores_fallback": env != "production"}
        return data

    @field_validator("env", mode="before")
    @classmethod
    def _normalise_env(cls, value: Any) -> Any:
        return value.strip().lower() if isinstance(value, str) else value

    @field_validator("database_url")
    @classmethod
    def _normalise_database_url(cls, value: str) -> str:
        return normalise_database_url(value)

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _parse_cors_origins(cls, value: Any) -> Any:
        items = value.split(",") if isinstance(value, str) else value
        if not isinstance(items, list | tuple):
            return value
        # Browsers send origins without a trailing slash; normalise so comparisons match.
        return [str(item).strip().rstrip("/") for item in items if str(item).strip()]

    @field_validator("admin_token")
    @classmethod
    def _blank_admin_token_is_unset(cls, value: SecretStr | None) -> SecretStr | None:
        if value is None or not value.get_secret_value().strip():
            return None
        return value

    @model_validator(mode="after")
    def _ensure_jwt_secret(self) -> Self:
        secret = self.jwt_secret.get_secret_value()
        if self.is_production:
            if len(secret) < MIN_JWT_SECRET_LENGTH:
                raise ValueError(
                    f"JWT_SECRET must be set to at least {MIN_JWT_SECRET_LENGTH} characters "
                    "when ENV=production"
                )
        elif not secret:
            logger.warning(
                "JWT_SECRET is not set: using a random per-process secret. "
                "Tokens will be invalidated on restart. Never do this in production."
            )
            self.jwt_secret = SecretStr(secrets.token_urlsafe(48))
        return self

    @model_validator(mode="after")
    def _ensure_strong_admin_token(self) -> Self:
        """In production, a set ADMIN_TOKEN must be long enough to resist guessing."""
        token = self.admin_token.get_secret_value() if self.admin_token else ""
        if self.is_production and token and len(token) < MIN_ADMIN_TOKEN_LENGTH:
            raise ValueError(
                f"ADMIN_TOKEN must be at least {MIN_ADMIN_TOKEN_LENGTH} characters "
                "when ENV=production"
            )
        return self


def normalise_database_url(url: str) -> str:
    """Point driver-less PostgreSQL URLs at psycopg 3; leave every other URL as is.

    ``postgres://`` and ``postgresql://`` become ``postgresql+psycopg://``. Only the scheme is
    rewritten: credentials, host, database and query string (``sslmode=require``,
    ``channel_binding=require``, ...) are kept byte for byte. URLs that already name a driver
    (``postgresql+asyncpg://``) and other databases (``sqlite:///``) are returned unchanged.
    """
    url = url.strip()
    scheme, separator, rest = url.partition("://")
    if separator and scheme.lower() in _DRIVERLESS_POSTGRES_SCHEMES:
        return f"{_POSTGRES_DRIVER_SCHEME}://{rest}"
    return url


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-wide settings (cached; call ``get_settings.cache_clear()`` in tests)."""
    return Settings()
