"""Deterministic daily demo prices (ARCHITECTURE.md section 6, "Demo prices").

Price = base price per product x chain-tier factor (discount 0.88-0.95, standard 0.97-1.05,
premium 1.08-1.20) x small daily jitter; about 12 % of offers on sale (10-35 % off). Everything
derives from (store chain or id, product slug, date) through SHA-256, so results are reproducible
across processes and machines, identical in every store of a chain, and change every day.
"""

from __future__ import annotations

import hashlib
import math
from datetime import date
from typing import TYPE_CHECKING

from app.data.catalog_seed import BASE_PRICES
from app.services.price_sources.base import PriceQuote, unit_price
from app.services.text import normalise_text

if TYPE_CHECKING:
    from app.models import Product, Store
    from app.schemas import PriceTier

# Chain tier -> (lowest, highest) factor applied to the base price.
TIER_FACTORS: dict[PriceTier, tuple[float, float]] = {
    "discount": (0.88, 0.95),
    "standard": (0.97, 1.05),
    "premium": (1.08, 1.20),
}
# Day-to-day variation around the chain price: +/- 3 %.
DAILY_JITTER = 0.03
SALE_PROBABILITY = 0.12
SALE_DISCOUNT_RANGE = (0.10, 0.35)
MIN_PRICE = 0.49


def stable_fraction(*parts: object) -> float:
    """Deterministic pseudo-random number in [0, 1) derived from ``parts``."""
    digest = hashlib.sha256("|".join(str(part) for part in parts).encode()).digest()
    return int.from_bytes(digest[:8], "big") / 2**64


def shelf_price(amount: float) -> float:
    """Round to a shelf-looking price ending in 9 cents (6.83 -> 6.89), never below 0.49."""
    dimes = math.floor(round(amount * 10, 6))
    return max(MIN_PRICE, round(dimes / 10 + 0.09, 2))


def pricing_key(store: Store) -> str:
    """Stores of the same chain share prices; independent stores are priced on their own."""
    chain = normalise_text(store.chain or "")
    return f"chain:{chain}" if chain else f"store:{store.id}"


class DemoPriceSource:
    """``PRICE_SOURCE=demo``: generated prices, flagged as demo everywhere in the UI."""

    name = "demo"
    is_demo = True

    def quote(self, store: Store, product: Product, day: date) -> PriceQuote | None:
        base_price = BASE_PRICES.get(product.slug)
        if base_price is None:
            # Not part of the demo catalog (e.g. removed from the seed): not sold.
            return None
        key = pricing_key(store)
        low, high = TIER_FACTORS[store.price_tier]
        # The chain factor is stable over time; only the jitter and the sales change daily.
        tier_factor = low + (high - low) * stable_fraction(key, product.slug, "tier")
        jitter = 1 + DAILY_JITTER * (2 * stable_fraction(key, product.slug, day, "jitter") - 1)
        regular_price = shelf_price(base_price * tier_factor * jitter)

        price = regular_price
        on_sale = stable_fraction(key, product.slug, day, "sale") < SALE_PROBABILITY
        if on_sale:
            low_cut, high_cut = SALE_DISCOUNT_RANGE
            cut = low_cut + (high_cut - low_cut) * stable_fraction(key, product.slug, day, "cut")
            price = shelf_price(regular_price * (1 - cut))
            if price >= regular_price:
                # Only possible for the cheapest items, where rounding eats the discount.
                on_sale, price = False, regular_price

        per_unit, per_unit_unit = unit_price(price, product.size_value, product.size_unit)
        return PriceQuote(
            price=price,
            regular_price=regular_price,
            on_sale=on_sale,
            unit_price=per_unit,
            unit_price_unit=per_unit_unit,
        )
