"""Daily refresh of stores and prices (ARCHITECTURE.md sections 1.4, 4 "Admin" and 6).

Runs three ways: ``POST /api/v1/admin/refresh`` (GitHub Actions cron), the command line
(``python -m app.jobs.refresh``), or in-process every 24 h when ``DAILY_REFRESH_IN_PROCESS`` is on.

One run re-discovers every area whose last discovery is about a day old (from Overpass, one area
at a time with a short pause, to respect its usage policy), then gives every known store
today's prices. Prices already written today are kept, so a second run the same day is cheap.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Callable
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import schemas
from app.config import Settings, get_settings
from app.db import Base, SessionLocal, utcnow
from app.models import AreaFetch, Store  # importing app.models registers every table
from app.services.catalog import seed_catalog
from app.services.stores import price_stores, refresh_area

logger = logging.getLogger(__name__)

DAILY_INTERVAL_S = 24 * 60 * 60
# The cron runs every 24 h: an area refreshed a little later during the previous run must still
# count as due, so "about a day old" means older than 23 h.
AREA_REFRESH_AGE = timedelta(hours=23)
# Pause between two Overpass queries of the same run.
OVERPASS_PAUSE_S = 1.0


def refresh_all(
    db: Session, *, settings: Settings, pause_s: float = OVERPASS_PAUSE_S
) -> schemas.RefreshResult:
    """Re-discover areas older than a day and re-price every store with the active price source.

    ``areas_refreshed`` counts areas whose store list was rebuilt, ``stores_refreshed`` the stores
    that received new prices and ``prices_updated`` the prices written.
    """
    started_at = utcnow()
    due = list(
        db.scalars(
            select(AreaFetch)
            .where(AreaFetch.fetched_at < started_at - AREA_REFRESH_AGE)
            .order_by(AreaFetch.fetched_at, AreaFetch.id)
        )
    )

    areas_refreshed = stores_refreshed = prices_updated = 0
    for position, area in enumerate(due):
        if position and pause_s > 0:
            time.sleep(pause_s)
        outcome = refresh_area(
            db, area.lat, area.lon, area.radius_km, settings=settings, force=True
        )
        areas_refreshed += int(outcome.discovered)
        stores_refreshed += outcome.pricing.stores_priced
        prices_updated += outcome.pricing.prices_written

    # Stores outside the refreshed areas (or whose area discovery failed) still get new prices.
    pricing = price_stores(
        db, list(db.scalars(select(Store).order_by(Store.id))), settings=settings
    )
    db.commit()
    stores_refreshed += pricing.stores_priced
    prices_updated += pricing.prices_written

    result = schemas.RefreshResult(
        areas_refreshed=areas_refreshed,
        stores_refreshed=stores_refreshed,
        prices_updated=prices_updated,
        started_at=started_at,
        finished_at=utcnow(),
    )
    logger.info(
        "Refresh done: %d areas, %d stores, %d prices",
        result.areas_refreshed,
        result.stores_refreshed,
        result.prices_updated,
    )
    return result


def _refresh_once(session_factory: Callable[[], Session]) -> schemas.RefreshResult:
    with session_factory() as db:
        return refresh_all(db, settings=get_settings())


async def run_daily_loop(
    session_factory: Callable[[], Session] = SessionLocal,
    *,
    interval_s: float = DAILY_INTERVAL_S,
) -> None:
    """Run ``refresh_all`` every ``interval_s`` seconds until cancelled (blocking work off-loop).

    The first run starts immediately. A failed run is logged and retried at the next interval.
    """
    while True:
        try:
            await asyncio.to_thread(_refresh_once, session_factory)
        except Exception:
            logger.exception("Daily refresh failed; next attempt in %s s", interval_s)
        await asyncio.sleep(interval_s)


def main() -> None:
    """Command-line entry point: run one refresh and print the result as JSON."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    settings = get_settings()
    with SessionLocal() as db:
        # A fresh database (first deploy, local run) gets its tables and catalog first.
        Base.metadata.create_all(bind=db.get_bind())
        seed_catalog(db)
        result = refresh_all(db, settings=settings)
    print(result.model_dump_json())


if __name__ == "__main__":
    main()
