"""Catalog seed, sections and the ``GET /catalog/offers`` query."""

from __future__ import annotations

from collections import defaultdict
from typing import Any, get_args

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import schemas
from app.config import Settings
from app.data import catalog_seed
from app.data.catalog_seed import PRODUCTS, SECTIONS
from app.models import Price, Product, Section, Store
from app.services.catalog import list_sections, search_offers, seed_catalog
from app.services.stores import ensure_area
from app.services.text import normalise_text

from .conftest import OutboundHttp
from .factories import HOME, install_overpass, seed, set_price, three_shops

SECTIONS_URL = "/api/v1/catalog/sections"
OFFERS_URL = "/api/v1/catalog/offers"


@pytest.fixture
def market(db: Session, outbound_http: OutboundHttp, settings: Settings) -> list[Store]:
    """Seeded catalog and three priced stores about 1.1, 2.2 and 3.3 km north of ``HOME``."""
    seed(db)
    install_overpass(outbound_http, three_shops())
    ensure_area(db, *HOME, 5, settings=settings)
    return list(db.scalars(select(Store).order_by(Store.lat)))


def offers(
    db: Session, settings: Settings, radius_km: float = 5, **params: Any
) -> schemas.OfferPage:
    query = schemas.OffersQuery(lat=HOME[0], lon=HOME[1], **params)
    return search_offers(db, query, radius_km=radius_km, settings=settings)


def product_total(db: Session) -> int:
    return db.scalar(select(func.count(Product.id))) or 0


# --------------------------------------------------------------------------------------------
# Seed data
# --------------------------------------------------------------------------------------------


def test_seed_is_large_enough() -> None:
    assert len(SECTIONS) >= 12
    assert len(PRODUCTS) >= 180


def test_seed_records_are_consistent() -> None:
    section_ids = {section.id for section in SECTIONS}
    dietary_tags = set(get_args(schemas.DietaryTag))
    size_units = set(get_args(schemas.SizeUnit))

    assert len({product.slug for product in PRODUCTS}) == len(PRODUCTS)
    assert len(section_ids) == len(SECTIONS)
    assert len({section.sort_order for section in SECTIONS}) == len(SECTIONS)
    for product in PRODUCTS:
        assert product.section_id in section_ids, product.slug
        assert set(product.tags) <= dietary_tags, product.slug
        assert product.size_unit in size_units, product.slug
        assert product.size_value > 0, product.slug
        assert 0.49 <= product.base_price <= 40, product.slug
        assert len(product.slug) <= 80 and product.slug == product.slug.lower()
        assert product.name_fr and product.name_en and product.brand
        assert product.keywords, product.slug
        for keyword in product.keywords:
            # Lower-case and accent-free, as the matching expects.
            assert keyword == normalise_text(keyword), (product.slug, keyword)


def test_every_section_has_products() -> None:
    assert {product.section_id for product in PRODUCTS} == {section.id for section in SECTIONS}


def test_each_kind_of_product_comes_in_one_to_three_brands() -> None:
    brands: defaultdict[tuple[str, float, str], set[str]] = defaultdict(set)
    for product in PRODUCTS:
        brands[(product.name_fr, product.size_value, product.size_unit)].add(product.brand)

    assert all(1 <= len(names) <= 3 for names in brands.values())


def test_brands_are_the_declared_fictional_ones() -> None:
    declared = {
        value.name for value in vars(catalog_seed).values() if isinstance(value, catalog_seed.Brand)
    }

    assert {product.brand for product in PRODUCTS} <= declared


def test_brand_tags_apply_to_their_products() -> None:
    for product in PRODUCTS:
        if product.brand == catalog_seed.PANIER_FUTE.name:
            assert "store_brand" in product.tags
        if product.brand == catalog_seed.TERRE_VIVACE.name:
            assert "organic" in product.tags
            assert "bio" in product.keywords


def test_base_prices_are_indexed_by_slug() -> None:
    assert catalog_seed.BASE_PRICES["lait-2-mont-bleuet"] == 6.89
    assert len(catalog_seed.BASE_PRICES) == len(PRODUCTS)


# --------------------------------------------------------------------------------------------
# Seeding
# --------------------------------------------------------------------------------------------


def test_seed_catalog_inserts_every_section_and_product(db: Session) -> None:
    seed_catalog(db)

    assert db.scalar(select(func.count(Section.id))) == len(SECTIONS)
    assert product_total(db) == len(PRODUCTS)
    milk = db.scalar(select(Product).where(Product.slug == "lait-2-terre-vivace"))
    assert milk is not None
    assert (milk.brand, milk.section_id, milk.size_value, milk.size_unit) == (
        "Terre Vivace",
        "dairy",
        4,
        "L",
    )
    assert "organic" in milk.tags


def test_seed_catalog_is_idempotent_and_restores_seed_values(db: Session) -> None:
    seed_catalog(db)
    product = db.scalar(select(Product).where(Product.slug == "bananes-hirondelle"))
    assert product is not None
    product_id = product.id
    product.name_en = "Changed"
    product.keywords = ["changed"]
    section = db.get(Section, "produce")
    assert section is not None
    section.name_fr = "Changé"
    db.commit()

    seed_catalog(db)
    seed_catalog(db)

    assert product_total(db) == len(PRODUCTS)
    assert db.scalar(select(func.count(Section.id))) == len(SECTIONS)
    db.refresh(product)
    db.refresh(section)
    assert (product.id, product.name_en) == (product_id, "Bananas")
    assert "banane" in product.keywords
    assert section.name_fr == "Fruits et légumes"


def test_seed_catalog_keeps_products_that_left_the_seed(db: Session) -> None:
    seed_catalog(db)
    db.add(
        Product(
            slug="ancien-produit",
            name_fr="Ancien",
            name_en="Old",
            brand="Marque Fictive",
            section_id="pantry",
            size_value=1,
            size_unit="unit",
            tags=[],
            keywords=["ancien"],
        )
    )
    db.commit()

    seed_catalog(db)

    assert product_total(db) == len(PRODUCTS) + 1


def test_list_sections_follows_the_display_order(db: Session) -> None:
    seed_catalog(db)

    assert [section.id for section in list_sections(db)] == [
        section.id for section in sorted(SECTIONS, key=lambda seed: seed.sort_order)
    ]


# --------------------------------------------------------------------------------------------
# GET /catalog/sections
# --------------------------------------------------------------------------------------------


def test_sections_endpoint_requires_authentication(client: TestClient) -> None:
    assert client.get(SECTIONS_URL).status_code == 401


def test_sections_endpoint_lists_the_seeded_sections(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    # The app seeds the catalog at startup.
    response = client.get(SECTIONS_URL, headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert len(body) == len(SECTIONS)
    assert body[0] == {
        "id": "produce",
        "name_fr": "Fruits et légumes",
        "name_en": "Fruits & vegetables",
    }


# --------------------------------------------------------------------------------------------
# Offers
# --------------------------------------------------------------------------------------------


def test_offers_default_to_the_cheapest_first(
    db: Session, settings: Settings, market: list[Store]
) -> None:
    page = offers(db, settings)

    assert page.total == 3 * product_total(db)
    assert len(page.items) == 30
    assert page.prices_are_demo is True
    prices = [offer.price for offer in page.items]
    assert prices == sorted(prices)
    assert all(offer.store.distance_km is not None for offer in page.items)


def test_offers_are_paginated_without_overlap(
    db: Session, settings: Settings, market: list[Store]
) -> None:
    first = offers(db, settings, limit=10, offset=0)
    second = offers(db, settings, limit=10, offset=10)
    both = offers(db, settings, limit=20, offset=0)

    ids = [offer.price_id for offer in first.items + second.items]
    assert ids == [offer.price_id for offer in both.items]
    assert len(set(ids)) == 20
    assert offers(db, settings, offset=10_000).items == []


def test_offers_sorted_by_unit_price(db: Session, settings: Settings, market: list[Store]) -> None:
    page = offers(db, settings, sort="unit_price", limit=100)

    unit_prices = [offer.unit_price for offer in page.items]
    assert unit_prices == sorted(unit_prices)


def test_offers_sorted_by_distance_then_price(
    db: Session, settings: Settings, market: list[Store]
) -> None:
    page = offers(db, settings, sort="distance", limit=100)

    keys = [(offer.store.distance_km, offer.price) for offer in page.items]
    assert keys == sorted(keys)
    assert {offer.store.id for offer in page.items} == {market[0].id}


def test_offers_search_text_matches_names_and_keywords(
    db: Session, settings: Settings, market: list[Store]
) -> None:
    page = offers(db, settings, q="Lait", limit=100)

    slugs = {offer.product.slug for offer in page.items}
    assert "lait-2-mont-bleuet" in slugs
    assert "lait-chocolat-mont-bleuet" in slugs
    assert all(
        "lait" in offer.product.slug or "boisson" in offer.product.slug for offer in page.items
    )
    assert offers(db, settings, q="zzzzqx").total == 0


def test_offers_filter_by_section_brand_and_tags(
    db: Session, settings: Settings, market: list[Store]
) -> None:
    dairy = offers(db, settings, section="dairy", limit=100)
    brand = offers(db, settings, brand="laiterie mont bleuet", limit=100)
    tags = offers(db, settings, tags="organic,vegan", limit=100)

    assert dairy.total > 0 and {offer.product.section_id for offer in dairy.items} == {"dairy"}
    assert brand.total > 0
    assert {offer.product.brand for offer in brand.items} == {"Laiterie Mont-Bleuet"}
    assert tags.total > 0
    assert all({"organic", "vegan"} <= set(offer.product.tags) for offer in tags.items)
    assert offers(db, settings, section="no-such-section").total == 0


def test_offers_filter_by_chain_and_store(
    db: Session, settings: Settings, market: list[Store]
) -> None:
    near, middle, _far = market

    by_chain = offers(db, settings, chain="EPICERIE clairiere", limit=100)
    by_store = offers(db, settings, store_id=near.id, limit=100)

    assert {offer.store.id for offer in by_chain.items} == {middle.id}
    assert by_chain.total == product_total(db)
    assert {offer.store.id for offer in by_store.items} == {near.id}


def test_offers_only_come_from_stores_within_the_radius(
    db: Session, settings: Settings, market: list[Store]
) -> None:
    near, _middle, far = market

    page = offers(db, settings, radius_km=1.5, limit=100)

    assert {offer.store.id for offer in page.items} == {near.id}
    assert offers(db, settings, radius_km=1.5, store_id=far.id).total == 0


def test_offers_filter_by_sale_and_price_range(
    db: Session, settings: Settings, market: list[Store]
) -> None:
    set_price(db, market[0], "bananes-hirondelle", 1.09, on_sale=True)

    on_sale = offers(db, settings, on_sale=True, limit=100)
    regular = offers(db, settings, on_sale=False, limit=100)
    ranged = offers(db, settings, min_price=2, max_price=3, limit=100)

    assert on_sale.total > 0 and all(offer.on_sale for offer in on_sale.items)
    assert on_sale.total + regular.total == 3 * product_total(db)
    assert all(not offer.on_sale for offer in regular.items)
    assert ranged.total > 0
    assert all(2 <= offer.price <= 3 for offer in ranged.items)


def test_offers_with_no_store_nearby_are_empty(db: Session, settings: Settings) -> None:
    seed(db)

    page = offers(db, settings)

    assert (page.items, page.total, page.prices_are_demo) == ([], 0, True)


def test_every_offer_matches_its_price_row(
    db: Session, settings: Settings, market: list[Store]
) -> None:
    (offer,) = offers(db, settings, limit=1).items
    row = db.get(Price, offer.price_id)

    assert row is not None
    assert (offer.price, offer.unit_price, offer.source) == (row.price, row.unit_price, "demo")
    assert offer.product.id == row.product_id and offer.store.id == row.store_id


# --------------------------------------------------------------------------------------------
# GET /catalog/offers
# --------------------------------------------------------------------------------------------


def test_offers_endpoint_requires_authentication(client: TestClient) -> None:
    assert client.get(OFFERS_URL, params={"lat": 45.5, "lon": -73.57}).status_code == 401


def test_offers_endpoint_discovers_the_area_and_filters(
    client: TestClient, auth_headers: dict[str, str], outbound_http: OutboundHttp
) -> None:
    install_overpass(outbound_http, three_shops())
    params = {
        "lat": HOME[0],
        "lon": HOME[1],
        "radius_km": 5,
        "tags": "vegan,gluten_free",
        "section": "produce",
        "sort": "distance",
        "limit": 5,
    }

    response = client.get(OFFERS_URL, params=params, headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["prices_are_demo"] is True
    assert body["total"] > 5
    assert len(body["items"]) == 5
    first = body["items"][0]
    assert first["store"]["name"] == "Marché Lumière"
    assert first["product"]["section_id"] == "produce"
    assert {"vegan", "gluten_free"} <= set(first["product"]["tags"])
    assert set(first) == {
        "price_id",
        "product",
        "store",
        "price",
        "regular_price",
        "on_sale",
        "unit_price",
        "unit_price_unit",
        "updated_at",
        "source",
    }


@pytest.mark.parametrize(
    "extra",
    [
        {"min_price": 5, "max_price": 1},
        {"limit": 0},
        {"limit": 101},
        {"offset": -1},
        {"sort": "name"},
        {"tags": "spicy"},
    ],
)
def test_offers_endpoint_validates_the_query(
    client: TestClient, auth_headers: dict[str, str], extra: dict[str, Any]
) -> None:
    params = {"lat": HOME[0], "lon": HOME[1], **extra}

    assert client.get(OFFERS_URL, params=params, headers=auth_headers).status_code == 422


def test_offers_endpoint_answers_503_without_stores_or_fallback(
    client: TestClient, auth_headers: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DEMO_STORES_FALLBACK", "false")
    from app.config import get_settings

    get_settings.cache_clear()

    response = client.get(OFFERS_URL, params={"lat": HOME[0], "lon": HOME[1]}, headers=auth_headers)

    assert response.status_code == 503
