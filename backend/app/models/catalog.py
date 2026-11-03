"""Stores, discovered areas, catalog sections, products and prices (ARCHITECTURE.md section 3)."""

from __future__ import annotations

from datetime import datetime
from typing import get_args

from sqlalchemy import JSON, CheckConstraint, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base, check_one_of, utcnow
from app.schemas import DietaryTag, PriceTier, SizeUnit, StoreSource, UnitPriceUnit


class Store(Base):
    """A grocery store, discovered from OpenStreetMap or synthesised as a labelled demo store."""

    __tablename__ = "stores"
    __table_args__ = (
        Index("ix_stores_lat_lon", "lat", "lon"),
        CheckConstraint(check_one_of("source", get_args(StoreSource)), name="ck_stores_source"),
        CheckConstraint(
            check_one_of("price_tier", get_args(PriceTier)), name="ck_stores_price_tier"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    # OSM element reference such as "node/123"; None for demo stores.
    osm_id: Mapped[str | None] = mapped_column(String(32), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    # OSM "brand" tag, else the store name.
    chain: Mapped[str | None] = mapped_column(String(200), index=True)
    address: Mapped[str | None] = mapped_column(String(300))
    lat: Mapped[float]
    lon: Mapped[float]
    source: Mapped[StoreSource] = mapped_column(String(8))
    price_tier: Mapped[PriceTier] = mapped_column(String(16), default="standard")
    last_seen_at: Mapped[datetime] = mapped_column(default=utcnow)

    prices: Mapped[list[Price]] = relationship(
        back_populates="store", cascade="all, delete-orphan", passive_deletes=True
    )

    def __repr__(self) -> str:
        return f"Store(id={self.id!r}, name={self.name!r})"


class AreaFetch(Base):
    """Marks an area (cell key from ``services.geo.area_cell_key``) as discovered."""

    __tablename__ = "area_fetches"

    id: Mapped[int] = mapped_column(primary_key=True)
    cell_key: Mapped[str] = mapped_column(String(64), unique=True)
    lat: Mapped[float]
    lon: Mapped[float]
    radius_km: Mapped[float]
    fetched_at: Mapped[datetime] = mapped_column(default=utcnow)

    def __repr__(self) -> str:
        return f"AreaFetch(cell_key={self.cell_key!r})"


class Section(Base):
    """Catalog section (aisle), identified by a slug such as ``"dairy"``."""

    __tablename__ = "sections"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    name_fr: Mapped[str] = mapped_column(String(80))
    name_en: Mapped[str] = mapped_column(String(80))
    sort_order: Mapped[int] = mapped_column(default=0)

    products: Mapped[list[Product]] = relationship(back_populates="section")

    def __repr__(self) -> str:
        return f"Section(id={self.id!r})"


class Product(Base):
    """Catalog product with fictional demo brand, bilingual names and matching keywords."""

    __tablename__ = "products"
    __table_args__ = (
        CheckConstraint(
            check_one_of("size_unit", get_args(SizeUnit)), name="ck_products_size_unit"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(80), unique=True)
    name_fr: Mapped[str] = mapped_column(String(120))
    name_en: Mapped[str] = mapped_column(String(120))
    brand: Mapped[str] = mapped_column(String(60), index=True)
    section_id: Mapped[str] = mapped_column(ForeignKey("sections.id"), index=True)
    size_value: Mapped[float]
    size_unit: Mapped[SizeUnit] = mapped_column(String(8))
    tags: Mapped[list[DietaryTag]] = mapped_column(JSON, default=list)
    # Lower-case, accent-free French and English synonyms used for matching.
    keywords: Mapped[list[str]] = mapped_column(JSON, default=list)

    section: Mapped[Section] = relationship(back_populates="products")
    prices: Mapped[list[Price]] = relationship(
        back_populates="product", cascade="all, delete-orphan", passive_deletes=True
    )

    def __repr__(self) -> str:
        return f"Product(id={self.id!r}, slug={self.slug!r})"


class Price(Base):
    """Price of one product in one store (CAD)."""

    __tablename__ = "prices"
    __table_args__ = (
        UniqueConstraint("store_id", "product_id", name="uq_prices_store_id_product_id"),
        CheckConstraint(
            check_one_of("unit_price_unit", get_args(UnitPriceUnit)),
            name="ck_prices_unit_price_unit",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id", ondelete="CASCADE"), index=True)
    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), index=True
    )
    price: Mapped[float]
    regular_price: Mapped[float]
    on_sale: Mapped[bool] = mapped_column(default=False)
    unit_price: Mapped[float]
    unit_price_unit: Mapped[UnitPriceUnit] = mapped_column(String(8))
    # Name of the price source that produced this price (e.g. "demo").
    source: Mapped[str] = mapped_column(String(32))
    updated_at: Mapped[datetime] = mapped_column(default=utcnow)

    store: Mapped[Store] = relationship(back_populates="prices")
    product: Mapped[Product] = relationship(back_populates="prices")

    def __repr__(self) -> str:
        return f"Price(store_id={self.store_id!r}, product_id={self.product_id!r})"
