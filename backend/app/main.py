"""FastAPI application factory (ARCHITECTURE.md section 2).

Run locally with ``uvicorn app.main:app --reload`` from the ``backend`` directory.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__, models  # noqa: F401  (models: registers every table on Base)
from app.config import get_settings
from app.db import Base, SessionLocal
from app.jobs.refresh import run_daily_loop
from app.routers import admin, auth, itinerary, lists, search, stores, users
from app.services.catalog import seed_catalog
from app.services.price_sources import get_price_source

API_PREFIX = "/api/v1"

logger = logging.getLogger(__name__)


def _initialise_database() -> None:
    """Create missing tables and (idempotently) seed the catalog."""
    with SessionLocal() as db:
        Base.metadata.create_all(bind=db.get_bind())
        seed_catalog(db)


def _log_task_failure(task: asyncio.Task[None]) -> None:
    if not task.cancelled() and task.exception() is not None:
        logger.error("Daily refresh loop stopped", exc_info=task.exception())


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    # Fail at startup, not on the first priced request, when PRICE_SOURCE names no source.
    get_price_source(settings.price_source)
    _initialise_database()

    refresh_task: asyncio.Task[None] | None = None
    if settings.daily_refresh_in_process:
        refresh_task = asyncio.create_task(run_daily_loop(), name="shopex-daily-refresh")
        refresh_task.add_done_callback(_log_task_failure)
    try:
        yield
    finally:
        if refresh_task is not None:
            refresh_task.cancel()
            await asyncio.gather(refresh_task, return_exceptions=True)


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="ShopEx API", version=__version__, lifespan=lifespan)

    # Auth uses bearer tokens, not cookies, so credentials are not needed for CORS.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
        # Lets the web client read how long a rate-limited login (429) must wait.
        expose_headers=["Retry-After"],
    )

    for router in (
        auth.router,
        users.router,
        lists.router,
        stores.router,
        search.router,
        itinerary.router,
        admin.router,
    ):
        app.include_router(router, prefix=API_PREFIX)
    return app


app = create_app()
