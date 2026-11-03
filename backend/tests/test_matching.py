"""Text normalisation, fuzzy product matching and the per-item search logic."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import schemas
from app.config import Settings
from app.models import GroceryList, Product, Store, User
from app.services.matching import (
    MAX_ALTERNATIVES,
    ListNotFoundError,
    ProductIndex,
    ScoredProduct,
    best_tier,
    brand_matches,
    default_list_name,
    match_products,
    normalise_text,
    search_grocery_list,
)
from app.services.stores import ensure_area
from app.services.text import significant_tokens

from .conftest import OutboundHttp
from .factories import HOME, install_overpass, seed, set_price, set_prices, three_shops

MILK_2 = ("lait-2-mont-bleuet", "lait-2-panier-fute", "lait-2-terre-vivace")


@pytest.fixture
def index(db: Session) -> ProductIndex:
    seed(db)
    return ProductIndex(db.scalars(select(Product).order_by(Product.id)))


@pytest.fixture
def market(db: Session, outbound_http: OutboundHttp, settings: Settings) -> list[Store]:
    """Seeded catalog and three priced stores: near (1.1 km), middle (2.2 km), far (3.3 km)."""
    seed(db)
    install_overpass(outbound_http, three_shops())
    ensure_area(db, *HOME, 5, settings=settings)
    return list(db.scalars(select(Store).order_by(Store.lat)))


def tier_slugs(index: ProductIndex, name: str) -> list[str]:
    return [scored.product.slug for scored in best_tier(index.rank(name))]


def request(*items: dict[str, Any], **extra: Any) -> schemas.SearchRequest:
    body = {"lat": HOME[0], "lon": HOME[1], "radius_km": 5, "items": list(items), **extra}
    return schemas.SearchRequest.model_validate(body)


def search(db: Session, user: User, settings: Settings, *items: dict[str, Any], **extra: Any):
    return search_grocery_list(db, user, request(*items, **extra), settings=settings)


def price_milk(db: Session, market: list[Store], prices: list[tuple[float, float, float]]) -> None:
    """Price the three 2 % milks (Mont-Bleuet, Panier Futé, Terre Vivace) in each store."""
    for store, store_prices in zip(market, prices, strict=True):
        set_prices(db, store, dict(zip(MILK_2, store_prices, strict=True)))


# --------------------------------------------------------------------------------------------
# Text
# --------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Crème 35 %", "creme 35"),
        ("  BEURRE   d'Arachide ", "beurre d arachide"),
        ("Œufs", "oeufs"),
        ("Bœuf haché", "boeuf hache"),
        ("Café-Crème", "cafe creme"),
        ("!!!", ""),
    ],
)
def test_normalise_text(text: str, expected: str) -> None:
    assert normalise_text(text) == expected


def test_significant_tokens_drop_stopwords_but_keep_tea() -> None:
    assert significant_tokens("Beurre d'arachide") == ("beurre", "arachide")
    assert significant_tokens("Thé") == ("the",)
    # Only stopwords: keep them rather than matching nothing.
    assert significant_tokens("de la") == ("de", "la")


# --------------------------------------------------------------------------------------------
# Product ranking
# --------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("lait", MILK_2),
        ("MILK", MILK_2),
        ("Œufs", ("oeufs-gros-belle-aube", "oeufs-gros-panier-fute", "oeufs-gros-terre-vivace")),
        ("bananne", ("bananes-hirondelle", "bananes-terre-vivace")),
        ("beurre d'arachide", ("beurre-arachide-belvue", "beurre-arachide-panier-fute")),
        ("ground beef", ("boeuf-hache-mi-maigre-rang-neuf", "boeuf-hache-mi-maigre-panier-fute")),
        ("pommes", ("pommes-mcintosh-ruisseau-clair", "pommes-mcintosh-terre-vivace")),
        ("patates", ("pommes-de-terre-recolte-nordet", "pommes-de-terre-panier-fute")),
        ("thé", ("the-noir-theiere-lunaire", "the-noir-panier-fute")),
        ("lait bio", ("lait-2-terre-vivace",)),
    ],
)
def test_best_tier_is_the_intended_product(
    index: ProductIndex, name: str, expected: tuple[str, ...]
) -> None:
    assert sorted(tier_slugs(index, name)) == sorted(expected)


def test_ranking_keeps_weaker_candidates_after_the_best(index: ProductIndex) -> None:
    ranked = index.rank("lait")
    slugs = [scored.product.slug for scored in ranked]

    assert "lait-chocolat-mont-bleuet" in slugs
    assert slugs.index("lait-chocolat-mont-bleuet") >= len(MILK_2)
    assert [scored.score for scored in ranked] == sorted((s.score for s in ranked), reverse=True)


@pytest.mark.parametrize("name", ["zzzzqx", "", "   ", "!!!"])
def test_unknown_names_match_nothing(index: ProductIndex, name: str) -> None:
    assert index.rank(name) == []


def test_empty_index_matches_nothing() -> None:
    assert ProductIndex([]).rank("lait") == []


def test_best_tier_of_nothing_is_empty() -> None:
    assert best_tier([]) == []


def test_best_tier_tolerance() -> None:
    first, second, third = (Product(id=index, slug=str(index)) for index in range(3))
    ranked = [ScoredProduct(first, 100), ScoredProduct(second, 95.5), ScoredProduct(third, 90)]

    assert [scored.product for scored in best_tier(ranked)] == [first, second]


@pytest.mark.parametrize(
    ("requested", "brand", "expected"),
    [
        ("Mont-Bleuet", "Laiterie Mont-Bleuet", True),
        ("laiterie mont bleuet", "Laiterie Mont-Bleuet", True),
        ("PRE DORE", "Pré Doré", True),
        ("Pré Doré", "Laiterie Mont-Bleuet", False),
        ("", "Pré Doré", False),
        ("!!", "Pré Doré", False),
    ],
)
def test_brand_matches(requested: str, brand: str, expected: bool) -> None:
    assert brand_matches(requested, brand) is expected


def test_match_products_prefers_the_requested_brand(db: Session) -> None:
    seed(db)

    assert [product.slug for product in match_products(db, "lait", brand="Pré Doré")] == [
        "lait-3-25-pre-dore"
    ]
    assert {product.slug for product in match_products(db, "lait", brand="Inconnue")} == set(MILK_2)
    assert {product.slug for product in match_products(db, "lait")} == set(MILK_2)


# --------------------------------------------------------------------------------------------
# Search: best offer and alternatives
# --------------------------------------------------------------------------------------------


def test_best_is_the_cheapest_and_alternatives_are_the_next_two(
    db: Session, user: User, settings: Settings, market: list[Store]
) -> None:
    near, middle, far = market
    price_milk(db, market, [(6.79, 6.49, 9.99), (6.59, 6.29, 9.49), (6.39, 5.99, 9.29)])

    response = search(db, user, settings, {"name": "lait", "quantity": 2})

    (result,) = response.results
    assert result.matched is True
    assert result.brand_matched is None
    assert result.message_key is None
    assert result.best is not None
    assert (result.best.store.id, result.best.product.slug, result.best.price) == (
        far.id,
        "lait-2-panier-fute",
        5.99,
    )
    assert [(offer.store.id, offer.price) for offer in result.alternatives] == [
        (middle.id, 6.29),
        (far.id, 6.39),
    ]
    assert len(result.alternatives) == MAX_ALTERNATIVES
    assert result.line_total == 11.98
    assert response.best_total == 11.98
    assert response.prices_are_demo is True
    assert response.currency == "CAD"


def test_equal_prices_prefer_the_nearest_store(
    db: Session, user: User, settings: Settings, market: list[Store]
) -> None:
    near, middle, far = market
    price_milk(db, market, [(7.0, 5.0, 9.0), (7.0, 5.0, 9.0), (7.0, 5.0, 9.0)])

    (result,) = search(db, user, settings, {"name": "lait"}).results

    assert result.best is not None
    assert result.best.store.id == near.id
    assert [offer.store.id for offer in result.alternatives] == [middle.id, far.id]
    assert result.best.store.distance_km == pytest.approx(1.11, abs=0.01)


def test_requested_brand_is_preferred_even_when_dearer(
    db: Session, user: User, settings: Settings, market: list[Store]
) -> None:
    price_milk(db, market, [(6.79, 6.49, 9.99), (6.59, 6.29, 9.49), (6.39, 5.99, 9.29)])

    (result,) = search(db, user, settings, {"name": "lait", "brand": "terre vivace"}).results

    assert result.brand_matched is True
    assert result.message_key is None
    assert result.best is not None
    assert (result.best.product.brand, result.best.price) == ("Terre Vivace", 9.29)
    assert {offer.product.brand for offer in result.alternatives} == {"Terre Vivace"}


def test_unknown_brand_falls_back_to_any_brand(
    db: Session, user: User, settings: Settings, market: list[Store]
) -> None:
    price_milk(db, market, [(6.79, 6.49, 9.99), (6.59, 6.29, 9.49), (6.39, 5.99, 9.29)])

    (result,) = search(db, user, settings, {"name": "lait", "brand": "Marque Inconnue"}).results

    assert result.matched is True
    assert result.brand_matched is False
    assert result.message_key == "search.brand_not_found"
    assert result.best is not None and result.best.price == 5.99


def test_brand_found_in_the_catalog_beyond_the_best_tier(
    db: Session, user: User, settings: Settings, market: list[Store]
) -> None:
    (result,) = search(db, user, settings, {"name": "lait", "brand": "Pré Doré"}).results

    assert result.brand_matched is True
    assert result.best is not None
    assert result.best.product.slug == "lait-3-25-pre-dore"


def test_unknown_item_is_reported_as_no_match(
    db: Session, user: User, settings: Settings, market: list[Store]
) -> None:
    response = search(
        db, user, settings, {"name": "zzzzqx", "brand": "Pré Doré"}, {"name": "bananes"}
    )

    missing, bananas = response.results
    assert missing.matched is False
    assert missing.best is None and missing.alternatives == []
    assert missing.line_total is None
    assert missing.brand_matched is False
    assert missing.message_key == "search.no_match"
    assert bananas.matched is True
    assert response.best_total == bananas.line_total


def test_no_store_in_range_means_no_match(
    db: Session, user: User, settings: Settings, market: list[Store]
) -> None:
    response = search(db, user, settings, {"name": "lait"}, radius_km=0.5)

    assert response.results[0].message_key == "search.no_match"
    assert response.stores == []
    assert response.best_total == 0


# --------------------------------------------------------------------------------------------
# Search: filters
# --------------------------------------------------------------------------------------------


def test_dietary_tags_select_a_matching_product(
    db: Session, user: User, settings: Settings, market: list[Store]
) -> None:
    (result,) = search(db, user, settings, {"name": "lait"}, filters={"tags": ["vegan"]}).results

    assert result.best is not None
    assert "vegan" in result.best.product.tags
    assert result.best.product.slug.startswith("boisson-")


def test_on_sale_only_and_max_price(
    db: Session, user: User, settings: Settings, market: list[Store]
) -> None:
    near, middle, far = market
    price_milk(db, market, [(6.79, 6.49, 9.99), (6.59, 6.29, 9.49), (6.39, 5.99, 9.29)])
    set_price(db, middle, "lait-2-terre-vivace", 8.49, on_sale=True)

    (on_sale,) = search(
        db, user, settings, {"name": "lait"}, filters={"on_sale_only": True}
    ).results
    (capped,) = search(db, user, settings, {"name": "lait"}, filters={"max_price": 6.3}).results

    assert on_sale.best is not None
    assert (on_sale.best.store.id, on_sale.best.price, on_sale.best.on_sale) == (
        middle.id,
        8.49,
        True,
    )
    assert all(offer.on_sale for offer in on_sale.alternatives)
    assert capped.best is not None
    assert all(offer.price <= 6.3 for offer in [capped.best, *capped.alternatives])
    assert [offer.price for offer in [capped.best, *capped.alternatives]] == [5.99, 6.29]


def test_excluded_chains_are_skipped(
    db: Session, user: User, settings: Settings, market: list[Store]
) -> None:
    near, middle, far = market
    price_milk(db, market, [(6.79, 6.49, 9.99), (6.59, 6.29, 9.49), (6.39, 5.99, 9.29)])

    (result,) = search(
        db, user, settings, {"name": "lait"}, filters={"exclude_chains": ["HALLES DU NORDET"]}
    ).results

    assert result.best is not None
    assert result.best.store.id == middle.id
    assert far.id not in {offer.store.id for offer in result.alternatives}


def test_sort_by_unit_price(
    db: Session, user: User, settings: Settings, market: list[Store]
) -> None:
    (by_price,) = search(db, user, settings, {"name": "lait chocolat"}).results
    (by_unit,) = search(
        db, user, settings, {"name": "lait chocolat"}, filters={"sort_by": "unit_price"}
    ).results

    assert by_price.best is not None and by_unit.best is not None
    unit_prices = [offer.unit_price for offer in [by_unit.best, *by_unit.alternatives]]
    assert unit_prices == sorted(unit_prices)


# --------------------------------------------------------------------------------------------
# Search: response totals and stores
# --------------------------------------------------------------------------------------------


def test_stores_are_the_unique_stores_of_the_best_offers_by_distance(
    db: Session, user: User, settings: Settings, market: list[Store]
) -> None:
    near, middle, far = market
    price_milk(db, market, [(6.79, 6.49, 9.99), (6.59, 6.29, 9.49), (6.39, 5.99, 9.29)])
    for store, price in zip(market, (1.19, 1.49, 1.59), strict=True):
        set_prices(db, store, {"bananes-hirondelle": price, "bananes-terre-vivace": 2.99})
    for store, price in zip(market, (3.99, 3.49, 3.89), strict=True):
        set_prices(db, store, {"fraises-recolte-nordet": 4.99, "fraises-hirondelle": price})

    response = search(
        db,
        user,
        settings,
        {"name": "lait"},
        {"name": "bananes", "quantity": 3},
        {"name": "fraises"},
    )

    assert [store.id for store in response.stores] == [near.id, middle.id, far.id]
    assert [store.distance_km for store in response.stores] == sorted(
        store.distance_km or 0 for store in response.stores
    )
    assert [result.line_total for result in response.results] == [5.99, 3.57, 3.49]
    assert response.best_total == 13.05


def test_default_list_names() -> None:
    moment = datetime(2026, 11, 2, 15, 0, tzinfo=UTC)

    assert default_list_name("fr", moment) == "Liste du 2 novembre 2026"
    assert default_list_name("en", moment) == "List of November 2, 2026"
    assert default_list_name("fr", moment.replace(day=1)) == "Liste du 1er novembre 2026"


def test_unsaved_search_does_not_touch_the_history(
    db: Session, user: User, settings: Settings, market: list[Store]
) -> None:
    response = search(db, user, settings, {"name": "lait"}, save_to_history=False, list_id=999)

    assert response.list_id is None
    assert db.scalar(select(GroceryList)) is None


def test_saving_into_someone_elses_list_is_refused_before_any_work(
    db: Session, user: User, settings: Settings, outbound_http: OutboundHttp
) -> None:
    seed(db)

    with pytest.raises(ListNotFoundError):
        search(db, user, settings, {"name": "lait"}, list_id=12345)

    assert outbound_http.requests == []
