"""Price-source registry, unit prices and the deterministic demo prices."""

from __future__ import annotations

from datetime import date, timedelta
from statistics import mean

import pytest

from app.data.catalog_seed import PRODUCTS
from app.models import Product, Store
from app.services import price_sources
from app.services.price_sources import (
    DemoPriceSource,
    PriceQuote,
    get_price_source,
    register_price_source,
    unit_price,
)
from app.services.price_sources import base as price_base
from app.services.price_sources.demo import (
    TIER_FACTORS,
    pricing_key,
    shelf_price,
    stable_fraction,
)

DAY = date(2026, 11, 2)
SOURCE = DemoPriceSource()


def make_store(store_id: int = 1, chain: str | None = "Marché Lumière", tier: str = "standard"):
    return Store(id=store_id, name=chain or "Épicerie", chain=chain, price_tier=tier)


def make_product(slug: str = "lait-2-mont-bleuet", size: float = 4, unit: str = "L") -> Product:
    return Product(slug=slug, size_value=size, size_unit=unit)


def quote(store: Store, product: Product, day: date = DAY) -> PriceQuote:
    result = SOURCE.quote(store, product, day)
    assert result is not None
    return result


# --------------------------------------------------------------------------------------------
# Registry
# --------------------------------------------------------------------------------------------


def test_demo_source_is_registered_and_flagged_as_demo() -> None:
    source = get_price_source("demo")

    assert isinstance(source, DemoPriceSource)
    assert source.name == "demo"
    assert source.is_demo is True


def test_unknown_source_raises_key_error_naming_the_known_ones() -> None:
    with pytest.raises(KeyError, match="registered: demo"):
        get_price_source("flyers")


def test_registering_a_source_makes_it_available(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(price_base, "_registry", dict(price_base._registry))

    class FixedSource:
        name = "fixed"
        is_demo = False

        def quote(self, store: Store, product: Product, day: date) -> PriceQuote | None:
            return PriceQuote(1.0, 1.0, False, 1.0, "unit")

    source = FixedSource()
    register_price_source(source)

    assert get_price_source("fixed") is source
    assert price_sources.get_price_source("demo").is_demo


# --------------------------------------------------------------------------------------------
# Unit prices and rounding
# --------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("price", "size", "unit", "expected"),
    [
        (4.99, 454, "g", (10.99, "kg")),
        (6.0, 1.5, "kg", (4.0, "kg")),
        (3.49, 500, "ml", (6.98, "L")),
        (6.89, 4, "L", (1.72, "L")),
        (4.29, 12, "unit", (0.36, "unit")),
    ],
)
def test_unit_price_per_kg_litre_or_unit(
    price: float, size: float, unit: str, expected: tuple[float, str]
) -> None:
    assert unit_price(price, size, unit) == expected  # type: ignore[arg-type]


def test_unit_price_rejects_an_empty_package() -> None:
    with pytest.raises(ValueError, match="positive"):
        unit_price(1.0, 0, "g")


@pytest.mark.parametrize(
    ("amount", "expected"),
    [(6.83, 6.89), (6.80, 6.89), (6.89, 6.89), (6.90, 6.99), (0.12, 0.49), (12.0, 12.09)],
)
def test_shelf_prices_end_in_nine_cents(amount: float, expected: float) -> None:
    assert shelf_price(amount) == expected


def test_stable_fraction_is_deterministic_and_in_unit_interval() -> None:
    values = [stable_fraction("chain:x", slug, DAY) for slug in ("a", "b", "c", "d")]

    assert values == [stable_fraction("chain:x", slug, DAY) for slug in ("a", "b", "c", "d")]
    assert all(0 <= value < 1 for value in values)
    assert len(set(values)) == len(values)


# --------------------------------------------------------------------------------------------
# Demo prices
# --------------------------------------------------------------------------------------------


def test_pricing_key_groups_stores_of_a_chain() -> None:
    assert pricing_key(make_store(1, "Marché Lumière")) == pricing_key(
        make_store(2, "MARCHE  LUMIERE")
    )
    assert pricing_key(make_store(3, None)) == "store:3"
    assert pricing_key(make_store(4, "  ")) == "store:4"


def test_quotes_are_deterministic() -> None:
    store, product = make_store(), make_product()

    assert quote(store, product) == quote(store, product)


def test_every_store_of_a_chain_has_the_same_price() -> None:
    product = make_product()

    assert quote(make_store(1), product) == quote(make_store(2), product)


def test_prices_change_from_day_to_day() -> None:
    store, product = make_store(), make_product()
    prices = {quote(store, product, DAY + timedelta(days=offset)).price for offset in range(10)}

    assert len(prices) > 1


def test_unknown_products_are_not_sold() -> None:
    assert SOURCE.quote(make_store(), make_product("not-in-the-catalog"), DAY) is None


@pytest.mark.parametrize("tier", list(TIER_FACTORS))
def test_regular_prices_follow_the_tier_factor(tier: str) -> None:
    low, high = TIER_FACTORS[tier]  # type: ignore[index]
    store = make_store(chain=f"Chaîne {tier}", tier=tier)
    for seed in PRODUCTS:
        result = quote(store, make_product(seed.slug, seed.size_value, seed.size_unit))
        # Daily jitter is +/- 3 % and rounding to a "...9" price adds less than 10 cents.
        assert seed.base_price * low * 0.97 - 0.01 <= result.regular_price
        assert result.regular_price <= max(seed.base_price * high * 1.03 + 0.1, 0.49)


def test_discount_chains_are_cheaper_than_premium_ones() -> None:
    def average_price(tier: str) -> float:
        store = make_store(chain="Chaîne témoin", tier=tier)
        return mean(
            quote(store, make_product(seed.slug, seed.size_value, seed.size_unit)).regular_price
            / seed.base_price
            for seed in PRODUCTS
        )

    assert average_price("discount") < average_price("standard") < average_price("premium")


def test_about_twelve_percent_of_offers_are_on_sale_with_ten_to_35_percent_off() -> None:
    quotes = [
        quote(
            make_store(chain=f"Chaîne {index % 5}"),
            make_product(seed.slug, seed.size_value, seed.size_unit),
            DAY + timedelta(days=index),
        )
        for index in range(20)
        for seed in PRODUCTS
    ]
    on_sale = [result for result in quotes if result.on_sale]

    assert 0.09 <= len(on_sale) / len(quotes) <= 0.15
    for result in on_sale:
        assert result.price < result.regular_price
        # Shelf rounding can move the effective discount a few points either way.
        assert 0.05 <= 1 - result.price / result.regular_price <= 0.36
    for result in quotes:
        if not result.on_sale:
            assert result.price == result.regular_price


def test_unit_price_matches_the_package() -> None:
    result = quote(make_store(), make_product("beurre-sale-mont-bleuet", 454, "g"))

    assert result.unit_price_unit == "kg"
    assert result.unit_price == pytest.approx(result.price * 1000 / 454, abs=0.01)
