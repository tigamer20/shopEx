"""Pluggable price sources (ARCHITECTURE.md sections 1.11 and 6).

Importing this package registers the shipped sources; pick one with ``PRICE_SOURCE``.
"""

from app.services.price_sources.base import (
    PriceQuote,
    PriceSource,
    get_price_source,
    register_price_source,
    unit_price,
)
from app.services.price_sources.demo import DemoPriceSource

register_price_source(DemoPriceSource())

__all__ = [
    "DemoPriceSource",
    "PriceQuote",
    "PriceSource",
    "get_price_source",
    "register_price_source",
    "unit_price",
]
