"""Store discovery: Overpass queries, area caching, store pricing and demo-store fallback.

Implements ARCHITECTURE.md sections 1.2, 3 (``Store``, ``AreaFetch``) and 6 (Overpass query,
``MAX_STORES_PER_AREA``, ``DEMO_STORES_FALLBACK``). OSM data is ODbL: responses that show it must
carry the "(c) OpenStreetMap contributors" attribution on the client.

An *area* is a grid cell plus a radius bucket (``services.geo.area_cell_key``). Discovering an
area queries Overpass around the cell centre, keeps the nearest ``MAX_STORES_PER_AREA`` stores,
upserts them by ``osm_id`` and prices every store of the area with the active price source.
"""

from __future__ import annotations

import logging
import math
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any

import httpx
from sqlalchemy import func, insert, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import __version__
from app.config import Settings
from app.db import utcnow
from app.models import AreaFetch, Price, Product, Store
from app.schemas import PriceTier
from app.services.geo import (
    area_cell_key,
    bounding_box,
    haversine_km,
    radius_bucket_km,
    snap_to_cell,
)
from app.services.price_sources import get_price_source
from app.services.price_sources.demo import stable_fraction
from app.services.text import normalise_text

logger = logging.getLogger(__name__)

USER_AGENT = f"ShopEx/{__version__} (grocery price comparison)"
# Extra HTTP read time beyond the Overpass query timeout (seconds).
OVERPASS_TIMEOUT_GRACE_S = 5.0
GROCERY_SHOP_TYPES = ("supermarket", "grocery", "greengrocer", "wholesale")
_SHOP_FILTER = f'["shop"~"^({"|".join(GROCERY_SHOP_TYPES)})$"]'

# An area is fresh for 24 h (ARCHITECTURE.md section 3).
AREA_TTL = timedelta(hours=24)
# After a failed discovery, try Overpass again after this delay rather than on every request.
FAILED_DISCOVERY_RETRY = timedelta(hours=1)
# Requests are snapped to the cell centre, up to half a cell diagonal away (0.025 deg in each
# direction, at most 3.93 km); querying this much further keeps their whole radius covered.
CELL_MARGIN_KM = 4.0

# Name used when OSM has no name nor brand for a shop.
_GENERIC_NAMES = {
    "supermarket": "Supermarché",
    "grocery": "Épicerie",
    "greengrocer": "Fruiterie",
    "wholesale": "Entrepôt alimentaire",
}
_NAME_MAX_LENGTH = 200
_ADDRESS_MAX_LENGTH = 300

# Chain -> tier table. Real chains are not named in code: the tier comes from generic words of
# the chain name or the OSM shop type, else from a stable hash of the chain name (about 25 %
# discount, 55 % standard, 20 % premium), so every store of a chain always gets the same tier.
TIER_KEYWORDS: dict[PriceTier, frozenset[str]] = {
    "discount": frozenset(
        {"discount", "escompte", "entrepot", "warehouse", "wholesale", "grossiste", "aubaine"}
    ),
    "premium": frozenset(
        {"bio", "biologique", "organic", "gourmet", "gourmand", "gourmandes", "fine", "fins"}
    ),
}
_HASHED_TIER_SHARES: tuple[tuple[PriceTier, float], ...] = (
    ("discount", 0.25),
    ("standard", 0.80),
    ("premium", 1.0),
)

# Fallback demo stores: fictional names, clearly labelled, never mistaken for OSM data.
DEMO_STORES: tuple[tuple[str, PriceTier], ...] = (
    ("Super Aubaine (démo)", "discount"),
    ("Marché Lumière (démo)", "standard"),
    ("Épicerie du Quartier (démo)", "standard"),
    ("Fruiterie Soleil (démo)", "standard"),
    ("Entrepôt Futé (démo)", "discount"),
    ("Halles Gourmandes (démo)", "premium"),
)
DEMO_STORE_ADDRESS = "Magasin de démonstration, emplacement fictif"
_KM_PER_DEGREE_LAT = 111.32


class StoreDiscoveryError(Exception):
    """Overpass answered, but not with usable data."""


class StoresUnavailableError(Exception):
    """Stores of an area cannot be discovered and no fallback applies (routers answer 503)."""


@dataclass(frozen=True, slots=True)
class DiscoveredStore:
    """A grocery store parsed from an Overpass element, before it is saved."""

    osm_id: str
    name: str
    chain: str | None
    address: str | None
    lat: float
    lon: float
    shop: str | None = None


@dataclass(frozen=True, slots=True)
class PricingStats:
    stores_priced: int = 0
    prices_written: int = 0


@dataclass(frozen=True, slots=True)
class AreaRefresh:
    """Outcome of ``refresh_area``."""

    area: AreaFetch
    # True when the store list was (re)built: from Overpass or from the demo fallback.
    discovered: bool
    pricing: PricingStats


# --------------------------------------------------------------------------------------------
# Overpass
# --------------------------------------------------------------------------------------------


def overpass_query(lat: float, lon: float, radius_km: float, *, timeout_s: float) -> str:
    """Overpass QL for grocery shops (nodes and ways) around a point, with way centres."""
    around = f"(around:{round(radius_km * 1000)},{lat:.6f},{lon:.6f})"
    return (
        f"[out:json][timeout:{max(1, math.ceil(timeout_s))}];"
        f"(node{_SHOP_FILTER}{around};way{_SHOP_FILTER}{around};);"
        "out center tags;"
    )


def fetch_overpass_stores(
    lat: float,
    lon: float,
    radius_km: float,
    *,
    settings: Settings,
    client: httpx.Client | None = None,
) -> list[DiscoveredStore]:
    """Query Overpass for ``shop ~ ^(supermarket|grocery|greengrocer|wholesale)$`` nodes/ways.

    Sends a ``User-Agent: ShopEx/<version>`` header. ``OVERPASS_TIMEOUT_S`` is both the
    server-side query timeout and, plus a short grace period, the HTTP read timeout. Raises
    ``httpx.HTTPError`` when Overpass is unreachable or answers with an error, and
    ``StoreDiscoveryError`` when the answer is not usable. Results are unique by ``osm_id``.
    """
    query = overpass_query(lat, lon, radius_km, timeout_s=settings.overpass_timeout_s)
    request_args: dict[str, Any] = {
        "data": {"data": query},
        "headers": {"User-Agent": USER_AGENT, "Accept": "application/json"},
        # Overpass answers its own timeout with a remark; leave it time to send that answer.
        "timeout": settings.overpass_timeout_s + OVERPASS_TIMEOUT_GRACE_S,
    }
    if client is None:
        with httpx.Client() as owned_client:
            response = owned_client.post(settings.overpass_url, **request_args)
    else:
        response = client.post(settings.overpass_url, **request_args)
    response.raise_for_status()
    return parse_overpass_payload(_json_object(response))


def _json_object(response: httpx.Response) -> dict[str, Any]:
    try:
        payload = response.json()
    except ValueError as exc:
        raise StoreDiscoveryError("Overpass response is not JSON") from exc
    if not isinstance(payload, dict):
        raise StoreDiscoveryError("Overpass response is not a JSON object")
    return payload


def parse_overpass_payload(payload: dict[str, Any]) -> list[DiscoveredStore]:
    """Stores of an Overpass JSON answer; elements without coordinates are skipped."""
    remark = payload.get("remark")
    if isinstance(remark, str) and "error" in remark.lower():
        # Overpass reports query timeouts and memory exhaustion this way, with status 200.
        raise StoreDiscoveryError("Overpass reported an error")
    elements = payload.get("elements")
    if not isinstance(elements, list):
        raise StoreDiscoveryError("Overpass response has no element list")

    stores: dict[str, DiscoveredStore] = {}
    for element in elements:
        store = _parse_element(element)
        if store is not None:
            stores.setdefault(store.osm_id, store)
    return list(stores.values())


def _is_integer(value: Any) -> bool:
    # bool is an int subclass; JSON true/false is never a valid id.
    return isinstance(value, int) and not isinstance(value, bool)


def _coordinate(value: Any, limit: float) -> float | None:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    number = float(value)
    return number if math.isfinite(number) and -limit <= number <= limit else None


def _tag(tags: dict[str, Any], key: str, max_length: int = _NAME_MAX_LENGTH) -> str | None:
    value = tags.get(key)
    if not isinstance(value, str):
        return None
    cleaned = " ".join(value.split())
    return cleaned[:max_length] or None


def _parse_element(element: Any) -> DiscoveredStore | None:
    if not isinstance(element, dict):
        return None
    element_type, element_id = element.get("type"), element.get("id")
    if element_type not in ("node", "way") or not _is_integer(element_id):
        return None
    position = element if element_type == "node" else element.get("center")
    if not isinstance(position, dict):
        return None
    lat, lon = _coordinate(position.get("lat"), 90), _coordinate(position.get("lon"), 180)
    if lat is None or lon is None:
        return None

    raw_tags = element.get("tags")
    tags: dict[str, Any] = raw_tags if isinstance(raw_tags, dict) else {}
    shop = _tag(tags, "shop")
    brand = _tag(tags, "brand")
    name = _tag(tags, "name") or brand or _GENERIC_NAMES.get(shop or "", "Épicerie")
    return DiscoveredStore(
        osm_id=f"{element_type}/{element_id}",
        name=name,
        # ARCHITECTURE.md section 3: the OSM brand tag, else the name.
        chain=brand or _tag(tags, "name"),
        address=_format_address(tags),
        lat=lat,
        lon=lon,
        shop=shop,
    )


def _format_address(tags: dict[str, Any]) -> str | None:
    """``"1234 Rue Example, Ville"`` from the OSM ``addr:*`` tags, or None when absent."""
    street = " ".join(
        part for part in (_tag(tags, "addr:housenumber"), _tag(tags, "addr:street")) if part
    )
    parts = [part for part in (street, _tag(tags, "addr:city")) if part]
    return ", ".join(parts)[:_ADDRESS_MAX_LENGTH] if parts else None


# --------------------------------------------------------------------------------------------
# Chain tiers
# --------------------------------------------------------------------------------------------


def price_tier_for(chain: str | None, shop: str | None = None) -> PriceTier:
    """Price tier of a chain (see ``TIER_KEYWORDS``); deterministic for a given name."""
    if shop == "wholesale":
        return "discount"
    words = set(normalise_text(chain or "").split())
    for tier, keywords in TIER_KEYWORDS.items():
        if words & keywords:
            return tier
    if not words:
        return "standard"
    draw = stable_fraction("tier", " ".join(sorted(words)))
    return next(tier for tier, share in _HASHED_TIER_SHARES if draw < share)


# --------------------------------------------------------------------------------------------
# Queries
# --------------------------------------------------------------------------------------------


def resolve_radius_km(requested: float | None, default: float, settings: Settings) -> float:
    """The requested radius, else the user's default, capped at ``MAX_RADIUS_KM``."""
    return min(requested if requested is not None else default, settings.max_radius_km)


def stores_near(db: Session, lat: float, lon: float, radius_km: float) -> list[tuple[Store, float]]:
    """Known stores within ``radius_km`` as ``(store, distance_km)``, nearest first."""
    box = bounding_box(lat, lon, radius_km)
    candidates = db.scalars(
        select(Store).where(
            Store.lat.between(box.min_lat, box.max_lat),
            Store.lon.between(box.min_lon, box.max_lon),
        )
    )
    nearby = [
        (store, distance)
        for store in candidates
        if (distance := haversine_km(lat, lon, store.lat, store.lon)) <= radius_km
    ]
    nearby.sort(key=lambda pair: (pair[1], pair[0].id))
    return nearby


# --------------------------------------------------------------------------------------------
# Pricing
# --------------------------------------------------------------------------------------------


def price_stores(
    db: Session,
    stores: Sequence[Store],
    *,
    settings: Settings,
    day: date | None = None,
    force: bool = False,
) -> PricingStats:
    """Give every store a price for every product with the active price source.

    Prices already written today by the same source are kept unless ``force`` is set, so the
    call is cheap to repeat. Does not commit.
    """
    if not stores:
        return PricingStats()
    db.flush()
    source = get_price_source(settings.price_source)
    now = utcnow()
    day = day or now.date()
    products = list(db.scalars(select(Product).order_by(Product.id)))
    store_ids = [store.id for store in stores]
    existing = {
        (row.store_id, row.product_id): row
        for row in db.execute(
            select(
                Price.id, Price.store_id, Price.product_id, Price.updated_at, Price.source
            ).where(Price.store_id.in_(store_ids))
        )
    }

    inserts: list[dict[str, Any]] = []
    updates: list[dict[str, Any]] = []
    priced_store_ids: set[int] = set()
    for store in stores:
        for product in products:
            current = existing.get((store.id, product.id))
            is_fresh = (
                current is not None
                and current.updated_at.date() == day
                and current.source == source.name
            )
            if is_fresh and not force:
                continue
            quote = source.quote(store, product, day)
            if quote is None:
                continue
            values = {
                "price": quote.price,
                "regular_price": quote.regular_price,
                "on_sale": quote.on_sale,
                "unit_price": quote.unit_price,
                "unit_price_unit": quote.unit_price_unit,
                "source": source.name,
                "updated_at": now,
            }
            if current is None:
                inserts.append({"store_id": store.id, "product_id": product.id, **values})
            else:
                updates.append({"id": current.id, **values})
            priced_store_ids.add(store.id)

    if inserts:
        db.execute(insert(Price), inserts)
    if updates:
        db.execute(update(Price), updates)
    # Bulk statements bypass loaded objects: make loaded prices reload their new values.
    for loaded in list(db.identity_map.values()):
        if isinstance(loaded, Price):
            db.expire(loaded)
    return PricingStats(len(priced_store_ids), len(inserts) + len(updates))


def _prices_are_current(db: Session, stores: Sequence[Store], *, settings: Settings) -> bool:
    """Cheap check: does every store already have today's price for every product?"""
    if not stores:
        return True
    product_count = db.scalar(select(func.count(Product.id))) or 0
    count, oldest = db.execute(
        select(func.count(Price.id), func.min(Price.updated_at)).where(
            Price.store_id.in_([store.id for store in stores]),
            Price.source == settings.price_source,
        )
    ).one()
    if count < len(stores) * product_count:
        return False
    return oldest is None or _as_utc_date(oldest) == utcnow().date()


def _as_utc_date(value: datetime) -> date:
    # Aggregates bypass the UTCDateTime column type: SQLite hands back naive UTC (or a string).
    if isinstance(value, str):
        value = datetime.fromisoformat(value)
    return value.date() if value.tzinfo is None else value.astimezone(UTC).date()


# --------------------------------------------------------------------------------------------
# Areas
# --------------------------------------------------------------------------------------------


def ensure_area(
    db: Session,
    lat: float,
    lon: float,
    radius_km: float,
    *,
    settings: Settings,
    force: bool = False,
) -> AreaFetch:
    """Make sure the stores around a point are known and priced.

    Re-fetches when the area is missing, older than 24 h, or ``force`` is set; keeps the nearest
    ``MAX_STORES_PER_AREA`` stores; falls back to labelled demo stores when Overpass fails and
    ``DEMO_STORES_FALLBACK`` is on (else raises ``StoresUnavailableError``, which routers map to
    503). A stale area whose refresh fails keeps its known stores. Commits.
    """
    return refresh_area(db, lat, lon, radius_km, settings=settings, force=force).area


def refresh_area(
    db: Session,
    lat: float,
    lon: float,
    radius_km: float,
    *,
    settings: Settings,
    force: bool = False,
) -> AreaRefresh:
    """``ensure_area`` with statistics, used by the daily refresh."""
    radius = min(radius_km, settings.max_radius_km)
    cell_key = area_cell_key(lat, lon, radius)
    try:
        return _refresh_area(db, lat, lon, radius, cell_key, settings=settings, force=force)
    except IntegrityError:
        # A concurrent request discovered the same area or stores first: use its work.
        db.rollback()
        area = db.scalar(select(AreaFetch).where(AreaFetch.cell_key == cell_key))
        if area is None:
            raise
        return AreaRefresh(area=area, discovered=False, pricing=PricingStats())


def _refresh_area(
    db: Session,
    lat: float,
    lon: float,
    radius: float,
    cell_key: str,
    *,
    settings: Settings,
    force: bool,
) -> AreaRefresh:
    centre_lat, centre_lon = snap_to_cell(lat, lon)
    bucket_km = radius_bucket_km(radius)
    coverage_km = bucket_km + CELL_MARGIN_KM
    now = utcnow()
    area = db.scalar(select(AreaFetch).where(AreaFetch.cell_key == cell_key))
    is_fresh = area is not None and now - area.fetched_at < AREA_TTL

    discovered = False
    if force or not is_fresh:
        try:
            found = fetch_overpass_stores(centre_lat, centre_lon, coverage_km, settings=settings)
        except (httpx.HTTPError, StoreDiscoveryError) as exc:
            logger.warning("Overpass unavailable for %s (%s)", cell_key, type(exc).__name__)
            if area is None and not settings.demo_stores_fallback:
                raise StoresUnavailableError("Store discovery is unavailable") from exc
            if area is None:
                _ensure_demo_stores(db, lat, lon, radius, cell_key, now=now)
                discovered = True
            # Retry Overpass in an hour instead of hammering it on every request.
            fetched_at = now - AREA_TTL + FAILED_DISCOVERY_RETRY
        else:
            nearest = _nearest(found, centre_lat, centre_lon, coverage_km, settings)
            _upsert_osm_stores(db, nearest, now=now)
            _remove_demo_stores(db, centre_lat, centre_lon, coverage_km)
            discovered = True
            fetched_at = now

        if area is None:
            area = AreaFetch(cell_key=cell_key, lat=centre_lat, lon=centre_lon, radius_km=bucket_km)
            db.add(area)
        area.fetched_at = fetched_at

    db.flush()
    stores = [store for store, _ in stores_near(db, centre_lat, centre_lon, coverage_km)]
    pricing = PricingStats()
    if discovered or force or not _prices_are_current(db, stores, settings=settings):
        pricing = price_stores(db, stores, settings=settings)
    db.commit()
    return AreaRefresh(area=area, discovered=discovered, pricing=pricing)


def _nearest(
    stores: Iterable[DiscoveredStore],
    lat: float,
    lon: float,
    radius_km: float,
    settings: Settings,
) -> list[DiscoveredStore]:
    """The ``MAX_STORES_PER_AREA`` stores closest to the point, within the radius."""
    with_distance = [
        (haversine_km(lat, lon, store.lat, store.lon), store.osm_id, store) for store in stores
    ]
    in_range = sorted(item for item in with_distance if item[0] <= radius_km)
    return [store for _, _, store in in_range[: settings.max_stores_per_area]]


def _upsert_osm_stores(db: Session, found: Sequence[DiscoveredStore], *, now: datetime) -> None:
    if not found:
        return
    known = {
        store.osm_id: store
        for store in db.scalars(select(Store).where(Store.osm_id.in_([s.osm_id for s in found])))
    }
    for item in found:
        store = known.get(item.osm_id)
        if store is None:
            store = Store(osm_id=item.osm_id, source="osm")
            db.add(store)
        store.name = item.name
        store.chain = item.chain
        store.address = item.address
        store.lat = item.lat
        store.lon = item.lon
        store.price_tier = price_tier_for(item.chain, item.shop)
        store.last_seen_at = now


def _remove_demo_stores(db: Session, lat: float, lon: float, radius_km: float) -> None:
    """Real stores replace the demo stores of an area once Overpass answers."""
    for store, _ in stores_near(db, lat, lon, radius_km):
        if store.source == "demo":
            db.delete(store)


def _ensure_demo_stores(
    db: Session, lat: float, lon: float, radius_km: float, cell_key: str, *, now: datetime
) -> None:
    """Add labelled demo stores around the point, unless stores are already known in range.

    Positions derive from the cell key, so the same area always gets the same demo stores.
    """
    if stores_near(db, lat, lon, radius_km):
        return
    km_per_degree_lon = _KM_PER_DEGREE_LAT * max(math.cos(math.radians(lat)), 0.01)
    for index, (name, tier) in enumerate(DEMO_STORES):
        angle = 2 * math.pi * stable_fraction(cell_key, index, "angle")
        distance_km = radius_km * (0.15 + 0.7 * stable_fraction(cell_key, index, "distance"))
        store_lat = lat + distance_km * math.cos(angle) / _KM_PER_DEGREE_LAT
        store_lon = lon + distance_km * math.sin(angle) / km_per_degree_lon
        db.add(
            Store(
                osm_id=None,
                name=name,
                chain=name,
                address=DEMO_STORE_ADDRESS,
                lat=round(min(max(store_lat, -90.0), 90.0), 6),
                lon=round(min(max(store_lon, -180.0), 180.0), 6),
                source="demo",
                price_tier=tier,
                last_seen_at=now,
            )
        )
