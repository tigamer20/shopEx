"""Store discovery: Overpass client, area cache, pricing, demo fallback and ``GET /stores``."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any
from urllib.parse import parse_qs

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import Settings
from app.db import utcnow
from app.models import AreaFetch, Price, Product, Store, User
from app.services import stores as stores_service
from app.services.geo import area_cell_key, haversine_km
from app.services.stores import (
    AREA_TTL,
    DEMO_STORES,
    FAILED_DISCOVERY_RETRY,
    OVERPASS_TIMEOUT_GRACE_S,
    StoreDiscoveryError,
    StoresUnavailableError,
    ensure_area,
    fetch_overpass_stores,
    overpass_query,
    parse_overpass_payload,
    price_stores,
    price_tier_for,
    refresh_area,
    resolve_radius_km,
    stores_near,
)

from .conftest import OutboundHttp
from .factories import (
    HOME,
    add_store,
    install_overpass,
    overpass_handler,
    overpass_node,
    overpass_way,
    seed,
    three_shops,
)

URL = "/api/v1/stores"


def count(db: Session, model: Any) -> int:
    return db.scalar(select(func.count()).select_from(model)) or 0


def product_count(db: Session) -> int:
    return count(db, Product)


@pytest.fixture
def seeded(db: Session) -> Session:
    seed(db)
    return db


def no_fallback(settings: Settings) -> Settings:
    return settings.model_copy(update={"demo_stores_fallback": False})


# --------------------------------------------------------------------------------------------
# Overpass client
# --------------------------------------------------------------------------------------------


def test_overpass_query_asks_for_grocery_nodes_and_ways_with_centres() -> None:
    query = overpass_query(45.5, -73.57, 2.5, timeout_s=2)

    assert query.startswith("[out:json][timeout:2];")
    assert '["shop"~"^(supermarket|grocery|greengrocer|wholesale)$"]' in query
    assert "node[" in query and "way[" in query
    assert "(around:2500,45.500000,-73.570000)" in query
    assert query.endswith("out center tags;")


def test_fetch_sends_the_query_with_user_agent_and_timeout(
    outbound_http: OutboundHttp, settings: Settings
) -> None:
    install_overpass(outbound_http, three_shops())

    found = fetch_overpass_stores(45.5, -73.57, 3, settings=settings)

    assert [store.osm_id for store in found] == ["node/101", "node/102", "way/201"]
    (request,) = outbound_http.requests
    assert request.method == "POST"
    assert str(request.url) == settings.overpass_url
    assert request.headers["User-Agent"].startswith("ShopEx/")
    assert request.extensions["timeout"]["read"] == (
        settings.overpass_timeout_s + OVERPASS_TIMEOUT_GRACE_S
    )
    sent = parse_qs(request.content.decode())["data"][0]
    assert sent == overpass_query(45.5, -73.57, 3, timeout_s=settings.overpass_timeout_s)
    assert sent.startswith("[out:json][timeout:3];")


def test_fetch_can_reuse_a_client(outbound_http: OutboundHttp, settings: Settings) -> None:
    install_overpass(outbound_http, three_shops())

    with httpx.Client() as client:
        found = fetch_overpass_stores(45.5, -73.57, 3, settings=settings, client=client)

    assert len(found) == 3


@pytest.mark.parametrize("status_code", [400, 429, 500, 504])
def test_fetch_raises_on_http_errors(
    outbound_http: OutboundHttp, settings: Settings, status_code: int
) -> None:
    outbound_http.install(overpass_handler([], status_code=status_code))

    with pytest.raises(httpx.HTTPStatusError):
        fetch_overpass_stores(45.5, -73.57, 3, settings=settings)


def test_fetch_raises_when_unreachable(settings: Settings) -> None:
    # The autouse guard makes every request fail like an unreachable host.
    with pytest.raises(httpx.ConnectError):
        fetch_overpass_stores(45.5, -73.57, 3, settings=settings)


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(200, text="<html>busy</html>"),
        httpx.Response(200, json=["not", "an", "object"]),
        httpx.Response(200, json={"version": 0.6}),
        httpx.Response(200, json={"elements": [], "remark": "runtime error: timeout"}),
    ],
)
def test_fetch_rejects_unusable_answers(
    outbound_http: OutboundHttp, settings: Settings, response: httpx.Response
) -> None:
    outbound_http.install(lambda request: response)

    with pytest.raises(StoreDiscoveryError):
        fetch_overpass_stores(45.5, -73.57, 3, settings=settings)


def test_parse_reads_nodes_ways_names_chains_and_addresses() -> None:
    payload = {
        "elements": [
            overpass_node(
                1,
                45.51,
                -73.57,
                shop="supermarket",
                name="Marché  Lumière Plateau",
                brand="Marché Lumière",
                **{
                    "addr:housenumber": "12",
                    "addr:street": "Rue des Érables",
                    "addr:city": "Ville",
                },
            ),
            overpass_way(2, 45.52, -73.58, shop="greengrocer", name="Fruiterie Soleil"),
            overpass_node(3, 45.53, -73.59, shop="wholesale", brand="Entrepôt Futé"),
            overpass_node(4, 45.54, -73.60, shop="grocery"),
            overpass_node(5, 45.55, -73.61, shop="grocery", **{"addr:street": "Rue Haute"}),
        ]
    }

    first, second, third, fourth, fifth = parse_overpass_payload(payload)

    assert (first.osm_id, first.name, first.chain) == (
        "node/1",
        "Marché Lumière Plateau",
        "Marché Lumière",
    )
    assert first.address == "12 Rue des Érables, Ville"
    assert (first.lat, first.lon, first.shop) == (45.51, -73.57, "supermarket")
    assert (second.osm_id, second.chain, second.address) == ("way/2", "Fruiterie Soleil", None)
    assert (second.lat, second.lon) == (45.52, -73.58)
    assert (third.name, third.chain) == ("Entrepôt Futé", "Entrepôt Futé")
    assert (fourth.name, fourth.chain) == ("Épicerie", None)
    assert fifth.address == "Rue Haute"


@pytest.mark.parametrize(
    "element",
    [
        "not an object",
        {"type": "relation", "id": 1, "center": {"lat": 45.5, "lon": -73.5}},
        {"type": "node", "id": "1", "lat": 45.5, "lon": -73.5},
        {"type": "node", "id": True, "lat": 45.5, "lon": -73.5},
        {"type": "node", "id": 1, "lat": 95.0, "lon": -73.5},
        {"type": "node", "id": 1, "lat": True, "lon": -73.5},
        {"type": "node", "id": 1, "lat": "45.5", "lon": -73.5},
        {"type": "way", "id": 1},
        {"type": "way", "id": 1, "center": {"lat": 45.5}},
    ],
)
def test_parse_skips_unusable_elements(element: Any) -> None:
    assert parse_overpass_payload({"elements": [element]}) == []


def test_parse_keeps_one_store_per_osm_id_and_tolerates_bad_tags() -> None:
    element = {"type": "node", "id": 7, "lat": 45.5, "lon": -73.5, "tags": "oops"}

    (store,) = parse_overpass_payload({"elements": [element, element]})

    assert (store.osm_id, store.name, store.chain, store.shop) == ("node/7", "Épicerie", None, None)


# --------------------------------------------------------------------------------------------
# Chain tiers
# --------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("chain", "shop", "expected"),
    [
        ("Anything", "wholesale", "discount"),
        ("Super Escompte du Coin", "supermarket", "discount"),
        ("Épicerie Bio Lumière", "grocery", "premium"),
        ("Aliments Fins Bellevue", None, "premium"),
        (None, None, "standard"),
        ("", "supermarket", "standard"),
    ],
)
def test_price_tier_from_words_and_shop_type(
    chain: str | None, shop: str | None, expected: str
) -> None:
    assert price_tier_for(chain, shop) == expected


def test_other_chains_get_a_stable_spread_of_tiers() -> None:
    names = [f"Marché Numéro {index}" for index in range(200)]
    tiers = [price_tier_for(name) for name in names]

    assert tiers == [price_tier_for(name.upper()) for name in names]
    assert {tier: tiers.count(tier) for tier in set(tiers)}.keys() == {
        "discount",
        "standard",
        "premium",
    }
    assert tiers.count("standard") > tiers.count("premium")


# --------------------------------------------------------------------------------------------
# Queries
# --------------------------------------------------------------------------------------------


def test_resolve_radius_defaults_and_caps(settings: Settings) -> None:
    assert resolve_radius_km(None, 10, settings) == 10
    assert resolve_radius_km(3.5, 10, settings) == 3.5
    assert resolve_radius_km(500, 10, settings) == settings.max_radius_km


def test_stores_near_filters_by_radius_and_sorts_by_distance(db: Session) -> None:
    lat, lon = HOME
    far = add_store(db, "Loin", lat + 0.05, lon)
    near = add_store(db, "Près", lat + 0.01, lon)
    middle = add_store(db, "Milieu", lat, lon + 0.03)
    add_store(db, "Hors zone", lat + 0.5, lon)

    found = stores_near(db, lat, lon, 6)

    assert [store.name for store, _ in found] == [near.name, middle.name, far.name]
    assert found[0][1] == pytest.approx(haversine_km(lat, lon, near.lat, near.lon))


# --------------------------------------------------------------------------------------------
# Areas
# --------------------------------------------------------------------------------------------


def test_ensure_area_discovers_saves_and_prices_the_stores(
    seeded: Session, outbound_http: OutboundHttp, settings: Settings
) -> None:
    install_overpass(outbound_http, three_shops())

    area = ensure_area(seeded, *HOME, 5, settings=settings)

    assert area.cell_key == area_cell_key(*HOME, 5)
    assert (area.lat, area.lon, area.radius_km) == (45.5, -73.55, 5)
    stores = list(seeded.scalars(select(Store).order_by(Store.osm_id)))
    assert [store.osm_id for store in stores] == ["node/101", "node/102", "way/201"]
    assert {store.source for store in stores} == {"osm"}
    assert count(seeded, Price) == 3 * product_count(seeded)
    assert {price.source for price in seeded.scalars(select(Price))} == {"demo"}


def test_a_fresh_area_is_served_from_the_cache(
    seeded: Session, outbound_http: OutboundHttp, settings: Settings
) -> None:
    install_overpass(outbound_http, three_shops())
    ensure_area(seeded, *HOME, 5, settings=settings)

    # Same cell and radius bucket, slightly different point and radius.
    ensure_area(seeded, HOME[0] + 0.01, HOME[1] + 0.01, 4, settings=settings)

    assert len(outbound_http.requests) == 1


def test_a_stale_area_is_discovered_again_and_stores_are_updated_in_place(
    seeded: Session, outbound_http: OutboundHttp, settings: Settings
) -> None:
    install_overpass(outbound_http, three_shops())
    area = ensure_area(seeded, *HOME, 5, settings=settings)
    area.fetched_at = utcnow() - AREA_TTL - timedelta(minutes=1)
    seeded.commit()
    renamed = three_shops()
    renamed[0]["tags"]["name"] = "Marché Lumière Rénové"
    install_overpass(outbound_http, renamed)

    ensure_area(seeded, *HOME, 5, settings=settings)

    assert count(seeded, Store) == 3
    assert count(seeded, AreaFetch) == 1
    store = seeded.scalar(select(Store).where(Store.osm_id == "node/101"))
    assert store is not None
    assert store.name == "Marché Lumière Rénové"
    assert utcnow() - area.fetched_at < timedelta(minutes=1)


def test_force_rediscovers_a_fresh_area(
    seeded: Session, outbound_http: OutboundHttp, settings: Settings
) -> None:
    install_overpass(outbound_http, three_shops())
    ensure_area(seeded, *HOME, 5, settings=settings)

    outcome = refresh_area(seeded, *HOME, 5, settings=settings, force=True)

    assert len(outbound_http.requests) == 2
    assert outcome.discovered is True
    # The stores already have today's prices: they are kept.
    assert outcome.pricing.prices_written == 0


def test_only_the_nearest_stores_are_kept(
    seeded: Session, outbound_http: OutboundHttp, settings: Settings
) -> None:
    lat, lon = 45.5, -73.55  # the cell centre
    shops = [
        overpass_node(index, lat + index * 0.002, lon, shop="grocery", name=f"Épicerie {index}")
        for index in range(1, 6)
    ]
    shops.append(overpass_node(99, lat + 1, lon, shop="grocery", name="Trop loin"))
    install_overpass(outbound_http, list(reversed(shops)))

    ensure_area(
        seeded, lat, lon, 5, settings=settings.model_copy(update={"max_stores_per_area": 3})
    )

    names = sorted(seeded.scalars(select(Store.name)))
    assert names == ["Épicerie 1", "Épicerie 2", "Épicerie 3"]


def test_radius_is_capped_at_the_maximum(
    seeded: Session, outbound_http: OutboundHttp, settings: Settings
) -> None:
    install_overpass(outbound_http, [])

    area = ensure_area(seeded, *HOME, 500, settings=settings)

    assert area.radius_km == settings.max_radius_km


def test_overpass_failure_falls_back_to_labelled_demo_stores(
    seeded: Session, settings: Settings
) -> None:
    area = ensure_area(seeded, *HOME, 5, settings=settings)

    stores = list(seeded.scalars(select(Store)))
    assert len(stores) == len(DEMO_STORES)
    for store in stores:
        assert store.source == "demo"
        assert store.osm_id is None
        assert "(démo)" in store.name
        assert haversine_km(*HOME, store.lat, store.lon) <= 5
    assert count(seeded, Price) == len(DEMO_STORES) * product_count(seeded)
    # Overpass is retried after an hour instead of on every request.
    age = utcnow() - area.fetched_at
    assert (
        AREA_TTL - FAILED_DISCOVERY_RETRY
        <= age
        < AREA_TTL - FAILED_DISCOVERY_RETRY + timedelta(minutes=1)
    )


def test_demo_stores_are_created_once_and_replaced_by_real_ones(
    seeded: Session, outbound_http: OutboundHttp, settings: Settings
) -> None:
    ensure_area(seeded, *HOME, 5, settings=settings)
    ensure_area(seeded, *HOME, 5, settings=settings, force=True)
    assert count(seeded, Store) == len(DEMO_STORES)

    install_overpass(outbound_http, three_shops())
    ensure_area(seeded, *HOME, 5, settings=settings, force=True)

    assert {store.source for store in seeded.scalars(select(Store))} == {"osm"}
    assert count(seeded, Store) == 3
    assert count(seeded, Price) == 3 * product_count(seeded)


def test_no_demo_stores_where_stores_are_already_known(seeded: Session, settings: Settings) -> None:
    add_store(seeded, "Marché Connu", HOME[0] + 0.01, HOME[1], osm_id="node/5")

    ensure_area(seeded, *HOME, 5, settings=settings)

    assert [store.name for store in seeded.scalars(select(Store))] == ["Marché Connu"]


def test_without_fallback_an_unknown_area_is_unavailable(
    seeded: Session, settings: Settings
) -> None:
    with pytest.raises(StoresUnavailableError):
        ensure_area(seeded, *HOME, 5, settings=no_fallback(settings))

    assert count(seeded, Store) == 0
    assert count(seeded, AreaFetch) == 0


def test_a_stale_area_keeps_its_stores_when_overpass_fails(
    seeded: Session, outbound_http: OutboundHttp, settings: Settings
) -> None:
    install_overpass(outbound_http, three_shops())
    area = ensure_area(seeded, *HOME, 5, settings=settings)
    area.fetched_at = utcnow() - AREA_TTL - timedelta(hours=1)
    seeded.commit()
    outbound_http.block()

    outcome = refresh_area(seeded, *HOME, 5, settings=no_fallback(settings))

    assert outcome.discovered is False
    assert count(seeded, Store) == 3
    assert utcnow() - outcome.area.fetched_at > AREA_TTL - FAILED_DISCOVERY_RETRY


def test_concurrent_discovery_reuses_the_winner(
    seeded: Session, settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    winner = AreaFetch(cell_key=area_cell_key(*HOME, 5), lat=45.5, lon=-73.55, radius_km=5)
    seeded.add(winner)
    seeded.commit()

    def collide(*args: Any, **kwargs: Any) -> Any:
        raise IntegrityError("INSERT", {}, Exception("duplicate key"))

    monkeypatch.setattr(stores_service, "_refresh_area", collide)

    outcome = refresh_area(seeded, *HOME, 5, settings=settings)

    assert outcome.area.id == winner.id
    assert outcome.discovered is False


def test_a_collision_without_a_winner_is_raised(
    seeded: Session, settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    def collide(*args: Any, **kwargs: Any) -> Any:
        raise IntegrityError("INSERT", {}, Exception("duplicate key"))

    monkeypatch.setattr(stores_service, "_refresh_area", collide)

    with pytest.raises(IntegrityError):
        refresh_area(seeded, *HOME, 5, settings=settings)


def test_a_fresh_area_fills_in_missing_prices(
    seeded: Session, outbound_http: OutboundHttp, settings: Settings
) -> None:
    install_overpass(outbound_http, three_shops())
    ensure_area(seeded, *HOME, 5, settings=settings)
    for price in seeded.scalars(select(Price).limit(5)):
        seeded.delete(price)
    seeded.commit()

    ensure_area(seeded, *HOME, 5, settings=settings)

    assert len(outbound_http.requests) == 1
    assert count(seeded, Price) == 3 * product_count(seeded)


# --------------------------------------------------------------------------------------------
# Pricing
# --------------------------------------------------------------------------------------------


def test_price_stores_writes_each_price_once_a_day(seeded: Session, settings: Settings) -> None:
    store = add_store(seeded, "Marché Lumière", *HOME)
    products = product_count(seeded)

    first = price_stores(seeded, [store], settings=settings)
    again = price_stores(seeded, [store], settings=settings)
    forced = price_stores(seeded, [store], settings=settings, force=True)

    assert (first.stores_priced, first.prices_written) == (1, products)
    assert (again.stores_priced, again.prices_written) == (0, 0)
    assert forced.prices_written == products


def test_price_stores_updates_prices_on_a_new_day(
    seeded: Session, settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = add_store(seeded, "Marché Lumière", *HOME)
    price_stores(seeded, [store], settings=settings)
    seeded.commit()
    before = {row.product_id: row.price for row in seeded.scalars(select(Price))}
    tomorrow = utcnow() + timedelta(days=1)
    monkeypatch.setattr(stores_service, "utcnow", lambda: tomorrow)

    stats = price_stores(seeded, [store], settings=settings)
    seeded.commit()

    rows = list(seeded.scalars(select(Price)))
    assert stats.prices_written == len(rows) == len(before)
    assert {row.updated_at.date() for row in rows} == {tomorrow.date()}
    assert any(row.price != before[row.product_id] for row in rows)


def test_price_stores_skips_products_the_source_does_not_sell(
    seeded: Session, settings: Settings
) -> None:
    seeded.add(
        Product(
            slug="hors-catalogue",
            name_fr="Hors catalogue",
            name_en="Off catalog",
            brand="Marque Fictive",
            section_id="pantry",
            size_value=1,
            size_unit="unit",
            tags=[],
            keywords=[],
        )
    )
    store = add_store(seeded, "Marché Lumière", *HOME)

    stats = price_stores(seeded, [store], settings=settings, day=date(2026, 11, 2))

    assert stats.prices_written == product_count(seeded) - 1


def test_price_stores_without_stores_does_nothing(seeded: Session, settings: Settings) -> None:
    assert price_stores(seeded, [], settings=settings).prices_written == 0


# --------------------------------------------------------------------------------------------
# GET /stores
# --------------------------------------------------------------------------------------------


def test_stores_requires_authentication(client: TestClient) -> None:
    assert client.get(URL, params={"lat": 45.5, "lon": -73.57}).status_code == 401


def test_stores_lists_nearby_stores_nearest_first(
    client: TestClient, auth_headers: dict[str, str], outbound_http: OutboundHttp
) -> None:
    install_overpass(outbound_http, three_shops())

    response = client.get(URL, params={"lat": HOME[0], "lon": HOME[1]}, headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert [store["name"] for store in body] == [
        "Marché Lumière",
        "Épicerie Clairière",
        "Halles du Nordet",
    ]
    assert body[0]["distance_km"] == pytest.approx(1.11, abs=0.01)
    assert body[0]["source"] == "osm"
    assert set(body[0]) == {
        "id",
        "name",
        "chain",
        "address",
        "lat",
        "lon",
        "distance_km",
        "source",
        "price_tier",
    }


def test_stores_uses_the_radius_of_the_query_else_the_user(
    client: TestClient,
    auth_headers: dict[str, str],
    outbound_http: OutboundHttp,
    db: Session,
    user: User,
) -> None:
    install_overpass(outbound_http, three_shops())
    params = {"lat": HOME[0], "lon": HOME[1]}

    narrow = client.get(URL, params={**params, "radius_km": 2}, headers=auth_headers)
    user.search_radius_km = 1.5
    db.commit()
    default = client.get(URL, params=params, headers=auth_headers)

    assert [store["name"] for store in narrow.json()] == ["Marché Lumière"]
    assert [store["name"] for store in default.json()] == ["Marché Lumière"]


def test_stores_answers_503_when_discovery_is_unavailable(
    client: TestClient, auth_headers: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DEMO_STORES_FALLBACK", "false")
    from app.config import get_settings

    get_settings.cache_clear()

    response = client.get(URL, params={"lat": HOME[0], "lon": HOME[1]}, headers=auth_headers)

    assert response.status_code == 503
    assert "unavailable" in response.json()["detail"]


@pytest.mark.parametrize(
    "params",
    [{"lat": 91, "lon": 0}, {"lat": 45}, {"lat": 45, "lon": -73, "radius_km": 0}],
)
def test_stores_validates_the_query(
    client: TestClient, auth_headers: dict[str, str], params: dict[str, Any]
) -> None:
    assert client.get(URL, params=params, headers=auth_headers).status_code == 422
