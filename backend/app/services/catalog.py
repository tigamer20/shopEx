"""Catalog seeding and offer queries (ARCHITECTURE.md sections 1.3, 3 and 4 "Stores & catalog")."""

from __future__ import annotations

from collections.abc import Collection
from typing import Any

from sqlalchemy import Select, case, func, select
from sqlalchemy.orm import Session

from app import schemas
from app.config import Settings
from app.data.catalog_seed import PRODUCTS, SECTIONS
from app.models import Price, Product, Section
from app.services.matching import ProductIndex, brand_matches, has_tags
from app.services.price_sources import get_price_source
from app.services.stores import stores_near
from app.services.text import normalise_text

DISTANCE_DECIMALS = 2


def seed_catalog(db: Session) -> None:
    """Idempotently upsert sections (by id) and products (by slug) from ``data.catalog_seed``.

    Called at startup with a fresh session; commits its own changes. Rows that left the seed
    are kept: prices may still reference them (the demo source no longer prices them).
    """
    sections = {section.id: section for section in db.scalars(select(Section))}
    for seed in SECTIONS:
        section = sections.get(seed.id)
        if section is None:
            section = Section(id=seed.id)
            db.add(section)
        section.name_fr = seed.name_fr
        section.name_en = seed.name_en
        section.sort_order = seed.sort_order
    db.flush()

    products = {product.slug: product for product in db.scalars(select(Product))}
    for seed in PRODUCTS:
        product = products.get(seed.slug)
        if product is None:
            product = Product(slug=seed.slug)
            db.add(product)
        product.name_fr = seed.name_fr
        product.name_en = seed.name_en
        product.brand = seed.brand
        product.section_id = seed.section_id
        product.size_value = seed.size_value
        product.size_unit = seed.size_unit
        # New list objects so the JSON columns are seen as modified.
        product.tags = list(seed.tags)
        product.keywords = list(seed.keywords)
    db.commit()


def list_sections(db: Session) -> list[Section]:
    """All sections ordered by ``sort_order``."""
    return list(db.scalars(select(Section).order_by(Section.sort_order, Section.id)))


def _matching_product_ids(db: Session, query: schemas.OffersQuery) -> set[int] | None:
    """Ids of the products passing the product filters; None when no product filter is set."""
    if not (query.q or query.section or query.brand or query.tags):
        return None
    products = list(db.scalars(select(Product).order_by(Product.id)))
    if query.q:
        # Browsing shows every candidate, not only the best tier used by the search.
        products = [scored.product for scored in ProductIndex(products).rank(query.q)]
    if query.section:
        products = [product for product in products if product.section_id == query.section]
    if query.brand:
        brand = query.brand
        products = [product for product in products if brand_matches(brand, product.brand)]
    if query.tags:
        tags = query.tags
        products = [product for product in products if has_tags(product, tags)]
    return {product.id for product in products}


def _filtered(
    statement: Select[Any],
    query: schemas.OffersQuery,
    store_ids: Collection[int],
    product_ids: set[int] | None,
) -> Select[Any]:
    """Restrict a price query to the nearby stores and the offer filters of ``query``."""
    statement = statement.where(Price.store_id.in_(sorted(store_ids)))
    if product_ids is not None:
        statement = statement.where(Price.product_id.in_(sorted(product_ids)))
    if query.on_sale is not None:
        statement = statement.where(Price.on_sale == query.on_sale)
    if query.min_price is not None:
        statement = statement.where(Price.price >= query.min_price)
    if query.max_price is not None:
        statement = statement.where(Price.price <= query.max_price)
    return statement


def search_offers(
    db: Session, query: schemas.OffersQuery, *, radius_km: float, settings: Settings
) -> schemas.OfferPage:
    """Filter, sort and paginate the offers of the stores within ``radius_km`` of the query point.

    ``radius_km`` is already resolved (query value or the user's default, clamped to
    ``MAX_RADIUS_KM``). Sorting is by price, unit price or distance; ties are broken by
    distance, then price, then offer id, so pages are stable.
    """
    prices_are_demo = get_price_source(settings.price_source).is_demo
    nearby = stores_near(db, query.lat, query.lon, radius_km)
    if query.chain:
        chain = normalise_text(query.chain)
        nearby = [pair for pair in nearby if normalise_text(pair[0].chain or pair[0].name) == chain]
    if query.store_id is not None:
        nearby = [pair for pair in nearby if pair[0].id == query.store_id]
    distances = {store.id: distance for store, distance in nearby}
    product_ids = _matching_product_ids(db, query)
    if not distances or product_ids == set():
        return schemas.OfferPage(items=[], total=0, prices_are_demo=prices_are_demo)

    total = db.scalar(_filtered(select(func.count(Price.id)), query, distances, product_ids))
    distance = case(distances, value=Price.store_id, else_=0.0)
    if query.sort == "distance":
        order = (distance, Price.price, Price.id)
    elif query.sort == "unit_price":
        order = (Price.unit_price, distance, Price.price, Price.id)
    else:
        order = (Price.price, distance, Price.id)
    page = db.scalars(
        _filtered(select(Price), query, distances, product_ids)
        .order_by(*order)
        .offset(query.offset)
        .limit(query.limit)
    )
    items = [
        schemas.Offer.from_price(price, round(distances[price.store_id], DISTANCE_DECIMALS))
        for price in page
    ]
    return schemas.OfferPage(items=items, total=total or 0, prices_are_demo=prices_are_demo)
