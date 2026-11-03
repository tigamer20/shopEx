"""Test data builders for the stores, catalog, matching and search tests (no network)."""

from __future__ import annotations

from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import utcnow
from app.models import Price, Product, Store
from app.services.catalog import seed_catalog

from .conftest import OutboundHttp

# A point in a fictional neighbourhood; every helper below places stores relative to it.
HOME = (45.50, -73.57)
# One hundredth of a degree of latitude is about 1.11 km.
KM_PER_CENTI_DEGREE = 1.112


def overpass_node(osm_id: int, lat: float, lon: float, **tags: str) -> dict[str, Any]:
    return {"type": "node", "id": osm_id, "lat": lat, "lon": lon, "tags": tags}


def overpass_way(osm_id: int, lat: float, lon: float, **tags: str) -> dict[str, Any]:
    return {"type": "way", "id": osm_id, "center": {"lat": lat, "lon": lon}, "tags": tags}


def overpass_handler(elements: list[dict[str, Any]], status_code: int = 200) -> Any:
    def handle(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code, json={"version": 0.6, "elements": elements})

    return handle


def install_overpass(outbound_http: OutboundHttp, elements: list[dict[str, Any]]) -> None:
    outbound_http.install(overpass_handler(elements))


def three_shops() -> list[dict[str, Any]]:
    """Three fictional shops north of ``HOME``: about 1.1, 2.2 and 3.3 km away."""
    lat, lon = HOME
    return [
        overpass_node(101, lat + 0.01, lon, shop="supermarket", name="Marché Lumière"),
        overpass_node(102, lat + 0.02, lon, shop="grocery", name="Épicerie Clairière"),
        overpass_way(201, lat + 0.03, lon, shop="supermarket", name="Halles du Nordet"),
    ]


def seed(db: Session) -> None:
    seed_catalog(db)


def add_store(
    db: Session,
    name: str,
    lat: float,
    lon: float,
    *,
    chain: str | None = None,
    tier: str = "standard",
    source: str = "osm",
    osm_id: str | None = None,
) -> Store:
    store = Store(
        osm_id=osm_id,
        name=name,
        chain=chain if chain is not None else name,
        address=None,
        lat=lat,
        lon=lon,
        source=source,
        price_tier=tier,
    )
    db.add(store)
    db.commit()
    return store


def product(db: Session, slug: str) -> Product:
    found = db.scalar(select(Product).where(Product.slug == slug))
    assert found is not None, slug
    return found


def set_price(
    db: Session, store: Store, slug: str, price: float, *, on_sale: bool = False
) -> Price:
    """Overwrite one (already generated) demo price; it stays fresh for today."""
    row = db.scalar(
        select(Price).where(Price.store_id == store.id, Price.product_id == product(db, slug).id)
    )
    assert row is not None, (store.name, slug)
    row.price = price
    row.regular_price = round(price * 1.25, 2) if on_sale else price
    row.on_sale = on_sale
    row.unit_price = price
    row.updated_at = utcnow()
    db.commit()
    return row


def set_prices(db: Session, store: Store, prices: dict[str, float]) -> None:
    for slug, price in prices.items():
        set_price(db, store, slug, price)
