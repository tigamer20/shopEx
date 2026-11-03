"""Daily refresh job: ``refresh_all``, the in-process loop and the command line."""

from __future__ import annotations

import asyncio
import json
from datetime import timedelta
from typing import Any

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app import schemas
from app.config import Settings
from app.db import utcnow
from app.jobs import refresh
from app.jobs.refresh import AREA_REFRESH_AGE, refresh_all, run_daily_loop
from app.models import AreaFetch, Price, Product, Section, Store
from app.services import stores as stores_service
from app.services.stores import ensure_area

from .conftest import OutboundHttp
from .factories import HOME, add_store, install_overpass, seed, three_shops


def product_count(db: Session) -> int:
    return db.scalar(select(func.count(Product.id))) or 0


def make_stale(db: Session, area: AreaFetch, age: timedelta = timedelta(days=1)) -> None:
    area.fetched_at = utcnow() - age
    db.commit()


@pytest.fixture
def known_area(db: Session, outbound_http: OutboundHttp, settings: Settings) -> AreaFetch:
    seed(db)
    install_overpass(outbound_http, three_shops())
    area = ensure_area(db, *HOME, 5, settings=settings)
    outbound_http.requests.clear()
    return area


def test_refresh_with_an_empty_database(db: Session, settings: Settings) -> None:
    result = refresh_all(db, settings=settings)

    assert (result.areas_refreshed, result.stores_refreshed, result.prices_updated) == (0, 0, 0)
    assert result.started_at <= result.finished_at


def test_fresh_areas_are_not_queried_again(
    db: Session, settings: Settings, outbound_http: OutboundHttp, known_area: AreaFetch
) -> None:
    make_stale(db, known_area, AREA_REFRESH_AGE - timedelta(minutes=5))

    result = refresh_all(db, settings=settings)

    assert outbound_http.requests == []
    assert result.areas_refreshed == 0
    assert result.prices_updated == 0


def test_areas_about_a_day_old_are_discovered_again(
    db: Session, settings: Settings, outbound_http: OutboundHttp, known_area: AreaFetch
) -> None:
    make_stale(db, known_area, AREA_REFRESH_AGE + timedelta(minutes=5))
    shops = three_shops()
    shops[1]["tags"]["name"] = "Épicerie Clairière Agrandie"
    install_overpass(outbound_http, shops)

    result = refresh_all(db, settings=settings)

    assert len(outbound_http.requests) == 1
    assert result.areas_refreshed == 1
    db.expire_all()
    assert "Épicerie Clairière Agrandie" in set(db.scalars(select(Store.name)))
    assert utcnow() - known_area.fetched_at < timedelta(minutes=1)


def test_prices_are_renewed_once_per_day(
    db: Session,
    settings: Settings,
    known_area: AreaFetch,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert refresh_all(db, settings=settings).prices_updated == 0

    tomorrow = utcnow() + timedelta(days=1)
    monkeypatch.setattr(stores_service, "utcnow", lambda: tomorrow)
    result = refresh_all(db, settings=settings)

    assert result.stores_refreshed == 3
    assert result.prices_updated == 3 * product_count(db)
    db.expire_all()
    assert {price.updated_at.date() for price in db.scalars(select(Price))} == {tomorrow.date()}
    assert refresh_all(db, settings=settings).prices_updated == 0


def test_stores_outside_any_area_are_priced_too(db: Session, settings: Settings) -> None:
    seed(db)
    add_store(db, "Marché Isolé", 46.8, -71.2)

    result = refresh_all(db, settings=settings)

    assert (result.areas_refreshed, result.stores_refreshed) == (0, 1)
    assert result.prices_updated == product_count(db)


def test_a_failed_area_keeps_its_stores(
    db: Session, settings: Settings, outbound_http: OutboundHttp, known_area: AreaFetch
) -> None:
    make_stale(db, known_area)
    outbound_http.block()

    result = refresh_all(db, settings=settings.model_copy(update={"demo_stores_fallback": False}))

    assert result.areas_refreshed == 0
    assert db.scalar(select(func.count(Store.id))) == 3


def test_overpass_queries_are_spaced_out(
    db: Session,
    settings: Settings,
    outbound_http: OutboundHttp,
    known_area: AreaFetch,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ensure_area(db, 46.81, -71.21, 5, settings=settings)
    for area in db.scalars(select(AreaFetch)):
        make_stale(db, area)
    pauses: list[float] = []
    monkeypatch.setattr(refresh.time, "sleep", pauses.append)

    result = refresh_all(db, settings=settings, pause_s=0.5)

    assert result.areas_refreshed == 2
    assert pauses == [0.5]


def test_daily_loop_runs_repeatedly_and_survives_failures(
    session_factory: sessionmaker[Session], monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[str] = []
    done = asyncio.Event()

    def fake_refresh_all(db: Session, *, settings: Settings) -> schemas.RefreshResult:
        calls.append(type(db).__name__)
        if len(calls) == 1:
            raise RuntimeError("Overpass exploded")
        if len(calls) == 3:
            loop.call_soon_threadsafe(done.set)
        now = utcnow()
        return schemas.RefreshResult(
            areas_refreshed=0, stores_refreshed=0, prices_updated=0, started_at=now, finished_at=now
        )

    monkeypatch.setattr(refresh, "refresh_all", fake_refresh_all)

    async def scenario() -> None:
        task = asyncio.create_task(run_daily_loop(session_factory, interval_s=0))
        await asyncio.wait_for(done.wait(), timeout=5)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(scenario())
    finally:
        loop.close()

    assert calls[:3] == ["Session", "Session", "Session"]


def test_command_line_prepares_the_database_and_prints_the_result(
    session_factory: sessionmaker[Session],
    capsys: pytest.CaptureFixture[str],
    db: Session,
) -> None:
    refresh.main()

    printed: dict[str, Any] = json.loads(capsys.readouterr().out)
    assert set(printed) == {
        "areas_refreshed",
        "stores_refreshed",
        "prices_updated",
        "started_at",
        "finished_at",
    }
    assert db.scalar(select(func.count(Section.id))) > 0
