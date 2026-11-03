"""Application wiring: lifespan behaviour and the test-suite network guard."""

import asyncio
from collections.abc import Iterator

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import inspect
from sqlalchemy.orm import Session, sessionmaker

from app import main
from app.config import get_settings
from app.db import get_db
from tests.conftest import OutboundHttp


def test_startup_creates_every_table(
    client: TestClient, session_factory: sessionmaker[Session]
) -> None:
    with session_factory() as session:
        tables = set(inspect(session.get_bind()).get_table_names())

    assert {
        "users",
        "grocery_lists",
        "stores",
        "area_fetches",
        "sections",
        "products",
        "prices",
    } <= tables


def test_routes_are_mounted_under_api_v1() -> None:
    paths = set(main.create_app().openapi()["paths"])

    assert "/api/v1/health" in paths
    assert all(path.startswith("/api/v1/") for path in paths)


def test_in_process_refresh_loop_runs_and_is_cancelled_on_shutdown(
    monkeypatch: pytest.MonkeyPatch, session_factory: sessionmaker[Session]
) -> None:
    events: list[str] = []

    async def fake_loop() -> None:
        events.append("started")
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            events.append("cancelled")
            raise

    monkeypatch.setenv("DAILY_REFRESH_IN_PROCESS", "true")
    get_settings.cache_clear()
    monkeypatch.setattr(main, "run_daily_loop", fake_loop)
    app = main.create_app()

    def override_get_db() -> Iterator[Session]:
        with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        assert test_client.get("/api/v1/health").status_code == 200

    assert events == ["started", "cancelled"]


def test_startup_fails_fast_on_an_unknown_price_source(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PRICE_SOURCE", "no-such-source")
    get_settings.cache_clear()
    app = main.create_app()

    with pytest.raises(KeyError, match="no-such-source"), TestClient(app):
        pass


def test_real_outbound_http_is_blocked() -> None:
    with pytest.raises(httpx.ConnectError):
        httpx.get("https://example.org/")


def test_outbound_http_can_be_faked(outbound_http: OutboundHttp) -> None:
    outbound_http.install(lambda request: httpx.Response(200, json={"path": request.url.path}))

    async def fetch_async() -> httpx.Response:
        async with httpx.AsyncClient() as async_client:
            return await async_client.get("https://osrm.invalid/route")

    assert httpx.get("https://overpass.invalid/api").json() == {"path": "/api"}
    assert asyncio.run(fetch_async()).json() == {"path": "/route"}
    assert [request.url.host for request in outbound_http.requests] == [
        "overpass.invalid",
        "osrm.invalid",
    ]
