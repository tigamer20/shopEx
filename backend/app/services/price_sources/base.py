"""Price-source contract and registry (ARCHITECTURE.md sections 1.11 and 6, ``PRICE_SOURCE``).

A price source turns (store, product, day) into a ``PriceQuote``. The active source is chosen
with the ``PRICE_SOURCE`` setting; ``demo`` is the only one shipped in v1.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from app.models import Product, Store
    from app.schemas import SizeUnit, UnitPriceUnit


@dataclass(frozen=True, slots=True)
class PriceQuote:
    """One price for one product in one store, in CAD."""

    price: float
    regular_price: float
    on_sale: bool
    unit_price: float
    unit_price_unit: UnitPriceUnit


class PriceSource(Protocol):
    """Anything able to price a product in a store for a given day."""

    @property
    def name(self) -> str:
        """Registry key, also stored in ``Price.source``."""
        ...

    @property
    def is_demo(self) -> bool:
        """True when prices are generated (drives ``prices_are_demo`` in responses)."""
        ...

    def quote(self, store: Store, product: Product, day: date) -> PriceQuote | None:
        """Price of ``product`` in ``store`` on ``day``; None when the store does not sell it."""
        ...


_registry: dict[str, PriceSource] = {}


def register_price_source(source: PriceSource) -> None:
    """Make ``source`` available under ``source.name`` (replaces a source of the same name)."""
    _registry[source.name] = source


def get_price_source(name: str) -> PriceSource:
    """Return the registered source called ``name`` (raises ``KeyError`` when unknown)."""
    try:
        return _registry[name]
    except KeyError:
        known = ", ".join(sorted(_registry)) or "none"
        raise KeyError(f"Unknown price source {name!r} (registered: {known})") from None


# Unit-price basis of each package unit: (unit price unit, package units per basis unit).
_UNIT_PRICE_BASIS: dict[SizeUnit, tuple[UnitPriceUnit, float]] = {
    "g": ("kg", 1000.0),
    "kg": ("kg", 1.0),
    "ml": ("L", 1000.0),
    "L": ("L", 1.0),
    "unit": ("unit", 1.0),
}


def unit_price(price: float, size_value: float, size_unit: SizeUnit) -> tuple[float, UnitPriceUnit]:
    """Price per kg, per L or per unit of a package, rounded to the cent.

    ``unit_price(4.99, 454, "g")`` is ``(10.99, "kg")``.
    """
    if size_value <= 0:
        raise ValueError("size_value must be positive")
    basis_unit, units_per_basis = _UNIT_PRICE_BASIS[size_unit]
    return round(price * units_per_basis / size_value, 2), basis_unit
