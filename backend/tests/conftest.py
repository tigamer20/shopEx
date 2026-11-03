"""Shared pytest fixtures.

Every test gets fresh settings (runtime-generated secrets), a fresh in-memory SQLite database and
a guarantee that no real outbound HTTP request leaves the process. Fixtures:

- ``settings``       the active ``Settings`` (autouse); environment variables are set per test.
- ``outbound_http``  blocks real HTTP (autouse); ``outbound_http.install(handler)`` routes every
                     httpx request (sync or async) to a fake handler instead.
- ``engine`` / ``session_factory`` / ``db``  the per-test database; ``SessionLocal`` points at it.
- ``client``         ``TestClient`` on a new app (lifespan runs: tables + catalog seed).
- ``user`` / ``user_password`` / ``auth_headers``  a registered user and a bearer header for it.
- ``admin_headers``  the ``X-Admin-Token`` header matching the test ``ADMIN_TOKEN``.
"""

from __future__ import annotations

import secrets
from collections.abc import Callable, Iterator

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app import db as db_module
from app.config import Settings, get_settings
from app.db import Base, create_db_engine, get_db
from app.main import create_app
from app.models import User
from app.security import create_access_token, hash_password, login_rate_limiter

# ".invalid" never resolves (RFC 2606); requests are blocked before DNS anyway.
UNROUTABLE_OVERPASS_URL = "http://overpass.invalid/api/interpreter"
UNROUTABLE_OSRM_URL = "http://osrm.invalid"

OutboundHandler = Callable[[httpx.Request], httpx.Response]


@pytest.fixture(autouse=True)
def settings(monkeypatch: pytest.MonkeyPatch) -> Iterator[Settings]:
    """Hermetic configuration: every variable of ARCHITECTURE.md section 6 is set explicitly."""
    environment = {
        "ENV": "development",
        "DATABASE_URL": "sqlite://",
        "JWT_SECRET": secrets.token_urlsafe(48),
        "JWT_EXPIRE_MINUTES": "60",
        "CORS_ORIGINS": "http://localhost:8081",
        "ADMIN_TOKEN": secrets.token_urlsafe(32),
        "OVERPASS_URL": UNROUTABLE_OVERPASS_URL,
        "OSRM_URL": UNROUTABLE_OSRM_URL,
        "HTTP_TIMEOUT_S": "2",
        "OVERPASS_TIMEOUT_S": "3",
        "MAX_RADIUS_KM": "50",
        "MAX_STORES_PER_AREA": "60",
        "PRICE_SOURCE": "demo",
        "DEMO_STORES_FALLBACK": "true",
        "DAILY_REFRESH_IN_PROCESS": "false",
    }
    for name, value in environment.items():
        monkeypatch.setenv(name, value)
    get_settings.cache_clear()
    yield get_settings()
    get_settings.cache_clear()


class OutboundHttp:
    """Controls what httpx does for real (non-test-client) requests during a test."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self._monkeypatch = monkeypatch
        self.requests: list[httpx.Request] = []

    def block(self) -> None:
        """Make every outbound request fail like an unreachable host (``httpx.ConnectError``)."""

        def refuse(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("outbound HTTP is disabled in tests", request=request)

        self.install(refuse)

    def install(self, handler: OutboundHandler) -> None:
        """Answer every outbound httpx request with ``handler`` (see ``httpx.MockTransport``)."""
        transport = httpx.MockTransport(self._recording(handler))

        def handle_request(_self: httpx.HTTPTransport, request: httpx.Request) -> httpx.Response:
            return transport.handle_request(request)

        async def handle_async_request(
            _self: httpx.AsyncHTTPTransport, request: httpx.Request
        ) -> httpx.Response:
            return await transport.handle_async_request(request)

        self._monkeypatch.setattr(httpx.HTTPTransport, "handle_request", handle_request)
        self._monkeypatch.setattr(
            httpx.AsyncHTTPTransport, "handle_async_request", handle_async_request
        )

    def _recording(self, handler: OutboundHandler) -> OutboundHandler:
        def record(request: httpx.Request) -> httpx.Response:
            self.requests.append(request)
            return handler(request)

        return record


@pytest.fixture(autouse=True)
def outbound_http(monkeypatch: pytest.MonkeyPatch) -> OutboundHttp:
    guard = OutboundHttp(monkeypatch)
    guard.block()
    return guard


@pytest.fixture(autouse=True)
def _clear_login_rate_limiter() -> Iterator[None]:
    login_rate_limiter.clear()
    yield
    login_rate_limiter.clear()


@pytest.fixture
def engine(settings: Settings) -> Iterator[Engine]:
    """Fresh in-memory SQLite database; StaticPool keeps it alive across threads."""
    test_engine = create_db_engine("sqlite://", poolclass=StaticPool)
    Base.metadata.create_all(test_engine)
    yield test_engine
    test_engine.dispose()


@pytest.fixture
def session_factory(engine: Engine) -> Iterator[sessionmaker[Session]]:
    """Session factory on the test database; the app-wide ``SessionLocal`` is re-bound too."""
    original_bind = db_module.SessionLocal.kw["bind"]
    db_module.SessionLocal.configure(bind=engine)
    yield db_module.SessionLocal
    db_module.SessionLocal.configure(bind=original_bind)


@pytest.fixture
def db(session_factory: sessionmaker[Session]) -> Iterator[Session]:
    """Session for arranging and asserting data; commit so the API sees your changes."""
    with session_factory() as session:
        yield session


@pytest.fixture
def client(session_factory: sessionmaker[Session]) -> Iterator[TestClient]:
    app = create_app()

    def override_get_db() -> Iterator[Session]:
        with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def user_password() -> str:
    return secrets.token_urlsafe(16)


@pytest.fixture
def user(db: Session, user_password: str) -> User:
    account = User(
        email=f"user-{secrets.token_hex(4)}@example.com",
        password_hash=hash_password(user_password),
        display_name="Test User",
    )
    db.add(account)
    db.commit()
    db.refresh(account)
    return account


@pytest.fixture
def auth_headers(user: User, settings: Settings) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user.id, settings=settings)}"}


@pytest.fixture
def admin_headers(settings: Settings) -> dict[str, str]:
    assert settings.admin_token is not None
    return {"X-Admin-Token": settings.admin_token.get_secret_value()}
