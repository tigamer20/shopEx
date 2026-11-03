"""Settings parsing and production safety checks (ARCHITECTURE.md section 6)."""

import secrets

import pytest
from pydantic import ValidationError

from app.config import (
    MIN_ADMIN_TOKEN_LENGTH,
    MIN_JWT_SECRET_LENGTH,
    Settings,
    normalise_database_url,
)
from app.db import POSTGRES_POOL_RECYCLE_S, create_db_engine

# Shaped like a Neon pooled connection string; the host is fictional and never contacted.
NEON_QUERY = "sslmode=require&channel_binding=require"
NEON_HOST = "ep-demo-123456-pooler.us-east-2.aws.neon.tech"


def make_settings(**overrides: object) -> Settings:
    # Ignore any developer .env file so tests only see the fixture environment + overrides.
    return Settings(_env_file=None, **overrides)  # type: ignore[call-arg]


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("postgres://u:p@db:5432/shopex", "postgresql+psycopg://u:p@db:5432/shopex"),
        ("postgresql://u:p@db/shopex", "postgresql+psycopg://u:p@db/shopex"),
        # Neon pooled URL: the query string must survive untouched.
        (
            f"postgresql://u:p@{NEON_HOST}/shopex?{NEON_QUERY}",
            f"postgresql+psycopg://u:p@{NEON_HOST}/shopex?{NEON_QUERY}",
        ),
        (
            f"postgres://u:p@{NEON_HOST}:5432/shopex?{NEON_QUERY}",
            f"postgresql+psycopg://u:p@{NEON_HOST}:5432/shopex?{NEON_QUERY}",
        ),
        # Pasted values often carry stray whitespace; scheme names are case-insensitive.
        ("  postgresql://u:p@db/shopex\n", "postgresql+psycopg://u:p@db/shopex"),
        ("POSTGRES://u:p@db/shopex", "postgresql+psycopg://u:p@db/shopex"),
        # Percent-encoded credentials are not decoded or re-encoded.
        ("postgresql://u:p%40ss%2Fw@db/shopex", "postgresql+psycopg://u:p%40ss%2Fw@db/shopex"),
        # URLs that already name a driver, and other databases, are left alone.
        ("postgresql+psycopg://u:p@db/shopex", "postgresql+psycopg://u:p@db/shopex"),
        (
            f"postgresql+psycopg2://u:p@db/shopex?{NEON_QUERY}",
            f"postgresql+psycopg2://u:p@db/shopex?{NEON_QUERY}",
        ),
        ("postgresql+asyncpg://u:p@db/shopex", "postgresql+asyncpg://u:p@db/shopex"),
        ("sqlite:///./shopex.db", "sqlite:///./shopex.db"),
        ("sqlite://", "sqlite://"),
    ],
)
def test_database_url_is_normalised(raw: str, expected: str) -> None:
    assert normalise_database_url(raw) == expected
    assert make_settings(database_url=raw).database_url == expected


def test_database_url_from_the_environment_is_normalised(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", f"postgresql://u:p@{NEON_HOST}/shopex?{NEON_QUERY}")

    assert make_settings().database_url == (
        f"postgresql+psycopg://u:p@{NEON_HOST}/shopex?{NEON_QUERY}"
    )


def test_postgres_engine_survives_idle_connection_drops() -> None:
    # Creating an engine does not connect, so the fictional host is never contacted.
    engine = create_db_engine(f"postgresql+psycopg://u:p@{NEON_HOST}/shopex?{NEON_QUERY}")
    try:
        assert engine.dialect.driver == "psycopg"
        assert engine.pool._pre_ping is True
        assert engine.pool._recycle == POSTGRES_POOL_RECYCLE_S
        assert engine.url.query == {"sslmode": "require", "channel_binding": "require"}
    finally:
        engine.dispose()


def test_sqlite_engine_keeps_its_defaults() -> None:
    engine = create_db_engine("sqlite://")
    try:
        assert engine.pool._recycle == -1
        assert engine.pool._pre_ping is False
    finally:
        engine.dispose()


def test_cors_origins_are_parsed_from_a_comma_list(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CORS_ORIGINS", " https://app.example/, ,http://localhost:8081 ")

    assert make_settings().cors_origins == ["https://app.example", "http://localhost:8081"]


def test_production_requires_a_long_jwt_secret() -> None:
    short_secret = secrets.token_urlsafe(8)

    with pytest.raises(ValidationError) as excinfo:
        make_settings(env="production", jwt_secret=short_secret)

    assert "JWT_SECRET" in str(excinfo.value)
    assert short_secret not in str(excinfo.value)


def test_production_accepts_a_long_jwt_secret() -> None:
    secret = secrets.token_urlsafe(MIN_JWT_SECRET_LENGTH)

    settings = make_settings(env="PRODUCTION", jwt_secret=secret)

    assert settings.is_production
    assert settings.jwt_secret.get_secret_value() == secret


def test_development_generates_a_random_secret_with_a_warning(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.delenv("JWT_SECRET")

    first, second = make_settings(), make_settings()

    assert len(first.jwt_secret.get_secret_value()) >= MIN_JWT_SECRET_LENGTH
    assert first.jwt_secret != second.jwt_secret
    assert "JWT_SECRET is not set" in caplog.text


@pytest.mark.parametrize(("env", "expected"), [("development", True), ("production", False)])
def test_demo_stores_fallback_defaults_by_environment(
    monkeypatch: pytest.MonkeyPatch, env: str, expected: bool
) -> None:
    monkeypatch.delenv("DEMO_STORES_FALLBACK")
    monkeypatch.setenv("ENV", env)

    assert make_settings().demo_stores_fallback is expected


def test_explicit_demo_stores_fallback_wins(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENV", "production")
    monkeypatch.setenv("DEMO_STORES_FALLBACK", "true")

    assert make_settings().demo_stores_fallback is True


def test_blank_admin_token_disables_admin(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ADMIN_TOKEN", "   ")

    assert make_settings().admin_token is None


def test_production_rejects_a_short_admin_token() -> None:
    short_token = secrets.token_urlsafe(8)

    with pytest.raises(ValidationError) as excinfo:
        make_settings(env="production", admin_token=short_token)

    assert "ADMIN_TOKEN" in str(excinfo.value)
    assert short_token not in str(excinfo.value)


def test_production_accepts_a_long_or_unset_admin_token(monkeypatch: pytest.MonkeyPatch) -> None:
    token = secrets.token_urlsafe(MIN_ADMIN_TOKEN_LENGTH)

    assert make_settings(env="production", admin_token=token).admin_token is not None
    monkeypatch.delenv("ADMIN_TOKEN")
    assert make_settings(env="production").admin_token is None


def test_development_accepts_a_short_admin_token() -> None:
    assert make_settings(admin_token=secrets.token_urlsafe(8)).admin_token is not None
