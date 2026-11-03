"""Stores and catalog browsing (ARCHITECTURE.md section 4, "Stores & catalog").

All endpoints require a signed-in user:

- ``GET /stores``: stores around a point, nearest first; discovers and prices the area when it
  is not cached (``services.stores``). 503 when discovery fails and no fallback applies.
- ``GET /catalog/sections``: every catalog section, in display order.
- ``GET /catalog/offers``: filtered, sorted and paginated offers around a point.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy.orm import Session

from app import schemas
from app.config import Settings
from app.deps import AppSettings, CurrentUser, DbSession
from app.models import User
from app.services import catalog
from app.services.stores import (
    StoresUnavailableError,
    ensure_area,
    resolve_radius_km,
    stores_near,
)

router = APIRouter(tags=["stores"])

STORES_UNAVAILABLE_DETAIL = "Store discovery is temporarily unavailable, try again later"
DISTANCE_DECIMALS = 2


def stores_unavailable() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=STORES_UNAVAILABLE_DETAIL
    )


def _discover(
    db: Session,
    user: User,
    lat: float,
    lon: float,
    requested_radius_km: float | None,
    settings: Settings,
) -> float:
    """Make sure the area is discovered and priced; return the effective radius."""
    radius_km = resolve_radius_km(requested_radius_km, user.search_radius_km, settings)
    try:
        ensure_area(db, lat, lon, radius_km, settings=settings)
    except StoresUnavailableError:
        raise stores_unavailable() from None
    return radius_km


@router.get("/stores", response_model=list[schemas.Store])
def list_stores(
    query: Annotated[schemas.StoresQuery, Query()],
    user: CurrentUser,
    db: DbSession,
    settings: AppSettings,
) -> list[schemas.Store]:
    radius_km = _discover(db, user, query.lat, query.lon, query.radius_km, settings)
    return [
        schemas.Store.from_model(store, round(distance, DISTANCE_DECIMALS))
        for store, distance in stores_near(db, query.lat, query.lon, radius_km)
    ]


@router.get("/catalog/sections", response_model=list[schemas.Section])
def list_sections(_user: CurrentUser, db: DbSession) -> list[schemas.Section]:
    return [schemas.Section.model_validate(section) for section in catalog.list_sections(db)]


@router.get("/catalog/offers", response_model=schemas.OfferPage)
def list_offers(
    query: Annotated[schemas.OffersQuery, Query()],
    user: CurrentUser,
    db: DbSession,
    settings: AppSettings,
) -> schemas.OfferPage:
    radius_km = _discover(db, user, query.lat, query.lon, query.radius_km, settings)
    return catalog.search_offers(db, query, radius_km=radius_km, settings=settings)
