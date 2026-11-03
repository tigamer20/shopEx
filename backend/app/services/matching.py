"""Grocery list item -> offers: cheapest + 2 alternatives (ARCHITECTURE.md section 4 "Search").

Candidate products come from a fuzzy match (rapidfuzz) of the item name against product names
and keywords, accent- and case-insensitive, French and English. Candidate offers are their
prices in stores within the radius, after filters, sorted by price (or unit price) then distance.

Scoring a product for an item name:

- *coverage*: every word of the name is compared with every word of the product (names and
  keywords, stopwords removed) and keeps its best ``fuzz.ratio``; coverage is the mean, so
  typos and plurals still count ("bananne" ~ "banane", "pomme" ~ "pommes"). Products below
  ``MIN_COVERAGE`` are not candidates.
- *closeness*: the best ``fuzz.ratio`` between the whole name and one whole product phrase, so
  "lait" prefers the product whose keyword is exactly "lait" over "lait au chocolat".

The score mixes both; only the best tier (within ``BEST_TIER_TOLERANCE`` of the top score) is
kept for an item, so the cheapest offer is the cheapest *of the right product*.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime

from rapidfuzz import fuzz, process
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import schemas
from app.config import Settings
from app.db import utcnow
from app.models import GroceryList, Price, Product, Store, User
from app.services.price_sources import get_price_source
from app.services.stores import ensure_area, resolve_radius_km, stores_near
from app.services.text import normalise_text, significant_tokens

__all__ = [
    "ListNotFoundError",
    "ProductIndex",
    "ScoredProduct",
    "brand_matches",
    "match_products",
    "normalise_text",
    "search_grocery_list",
]

MIN_COVERAGE = 80.0
BEST_TIER_TOLERANCE = 5.0
COVERAGE_WEIGHT = 0.7
# Word similarities below this are treated as no similarity at all.
_TOKEN_SCORE_FLOOR = 50.0
BRAND_MATCH_THRESHOLD = 90.0
MAX_ALTERNATIVES = 2
DISTANCE_DECIMALS = 2

_MONTHS_FR = (
    "janvier", "février", "mars", "avril", "mai", "juin",
    "juillet", "août", "septembre", "octobre", "novembre", "décembre",
)  # fmt: skip
_MONTHS_EN = (
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
)  # fmt: skip


class ListNotFoundError(LookupError):
    """``list_id`` does not name a list of the caller (routers answer 404)."""


# --------------------------------------------------------------------------------------------
# Product matching
# --------------------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ScoredProduct:
    product: Product
    score: float


class ProductIndex:
    """Searchable view of the catalog; build once per request and rank many names."""

    def __init__(self, products: Iterable[Product]) -> None:
        self._products = list(products)
        vocabulary: dict[str, int] = {}
        self._product_tokens: list[frozenset[int]] = []
        self._phrases: list[str] = []
        self._phrase_owners: list[int] = []
        for position, product in enumerate(self._products):
            token_ids: set[int] = set()
            for text in (product.name_fr, product.name_en, *product.keywords):
                tokens = significant_tokens(text)
                token_ids.update(vocabulary.setdefault(token, len(vocabulary)) for token in tokens)
                self._phrases.append(" ".join(tokens))
                self._phrase_owners.append(position)
            self._product_tokens.append(frozenset(token_ids))
        self._vocabulary = list(vocabulary)

    def rank(self, name: str) -> list[ScoredProduct]:
        """Every candidate product for ``name``, best first (ties by id)."""
        query_tokens = significant_tokens(name)
        if not query_tokens or not self._products:
            return []
        word_scores = [
            {
                index: score
                for _, score, index in process.extract(
                    token,
                    self._vocabulary,
                    scorer=fuzz.ratio,
                    limit=None,
                    score_cutoff=_TOKEN_SCORE_FLOOR,
                )
            }
            for token in query_tokens
        ]
        closeness = [0.0] * len(self._products)
        for _, score, index in process.extract(
            " ".join(query_tokens), self._phrases, scorer=fuzz.ratio, limit=None
        ):
            owner = self._phrase_owners[index]
            closeness[owner] = max(closeness[owner], score)

        ranked: list[ScoredProduct] = []
        for position, token_ids in enumerate(self._product_tokens):
            coverage = sum(
                max((scores.get(token_id, 0.0) for token_id in token_ids), default=0.0)
                for scores in word_scores
            ) / len(word_scores)
            if coverage < MIN_COVERAGE:
                continue
            score = COVERAGE_WEIGHT * coverage + (1 - COVERAGE_WEIGHT) * closeness[position]
            ranked.append(ScoredProduct(self._products[position], round(score, 2)))
        ranked.sort(key=lambda scored: (-scored.score, scored.product.id))
        return ranked


def best_tier(ranked: Sequence[ScoredProduct]) -> list[ScoredProduct]:
    """The leading products of a ranking, within ``BEST_TIER_TOLERANCE`` of the best score."""
    if not ranked:
        return []
    threshold = ranked[0].score - BEST_TIER_TOLERANCE
    return [scored for scored in ranked if scored.score >= threshold]


def brand_matches(requested: str, brand: str) -> bool:
    """Whether a brand typed by the user designates ``brand`` (accents, case, partial name)."""
    wanted = normalise_text(requested)
    if not wanted:
        return False
    return fuzz.token_set_ratio(wanted, normalise_text(brand)) >= BRAND_MATCH_THRESHOLD


def has_tags(product: Product, tags: Iterable[str]) -> bool:
    return set(tags) <= set(product.tags)


def match_products(db: Session, name: str, *, brand: str | None = None) -> list[Product]:
    """Products matching an item name, best match first (brand-filtered when found)."""
    ranked = ProductIndex(db.scalars(select(Product).order_by(Product.id))).rank(name)
    if brand:
        branded = [scored for scored in ranked if brand_matches(brand, scored.product.brand)]
        ranked = branded or ranked
    return [scored.product for scored in best_tier(ranked)]


# --------------------------------------------------------------------------------------------
# Grocery list search
# --------------------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class _ItemCandidates:
    products: list[Product]
    # Best products of the requested brand; None when no brand was requested.
    brand_products: list[Product] | None


def _item_candidates(
    index: ProductIndex, item: schemas.GroceryItemInput, filters: schemas.SearchFilters
) -> _ItemCandidates:
    # Dietary tags describe the product, so they narrow candidates before the best tier is
    # chosen: "lait" + vegan finds the almond beverage rather than nothing.
    ranked = [scored for scored in index.rank(item.name) if has_tags(scored.product, filters.tags)]
    products = [scored.product for scored in best_tier(ranked)]
    if item.brand is None:
        return _ItemCandidates(products, None)
    branded = [scored for scored in ranked if brand_matches(item.brand, scored.product.brand)]
    return _ItemCandidates(products, [scored.product for scored in best_tier(branded)])


@dataclass(frozen=True, slots=True)
class _Offer:
    price: Price
    distance_km: float


def _offer_allowed(offer: _Offer, filters: schemas.SearchFilters, excluded: set[str]) -> bool:
    price = offer.price
    if filters.on_sale_only and not price.on_sale:
        return False
    if filters.max_price is not None and price.price > filters.max_price:
        return False
    return _chain_key(price.store) not in excluded


def _chain_key(store: Store) -> str:
    return normalise_text(store.chain or store.name)


def _sort_key(offer: _Offer, sort_by: schemas.SearchSortBy) -> tuple[float, ...]:
    price = offer.price
    primary = price.unit_price if sort_by == "unit_price" else price.price
    return (primary, offer.distance_km, price.price, price.id)


def _ranked_offers(
    products: Sequence[Product],
    offers_by_product: Mapping[int, Sequence[_Offer]],
    filters: schemas.SearchFilters,
    excluded: set[str],
) -> list[_Offer]:
    offers = [
        offer
        for product in products
        for offer in offers_by_product.get(product.id, ())
        if _offer_allowed(offer, filters, excluded)
    ]
    offers.sort(key=lambda offer: _sort_key(offer, filters.sort_by))
    return offers


def _distinct(offers: Iterable[_Offer], limit: int) -> list[_Offer]:
    """The first ``limit`` offers that are distinct by (product, store)."""
    chosen: list[_Offer] = []
    seen: set[tuple[int, int]] = set()
    for offer in offers:
        key = (offer.price.product_id, offer.price.store_id)
        if key in seen:
            continue
        seen.add(key)
        chosen.append(offer)
        if len(chosen) == limit:
            break
    return chosen


def _to_schema(offer: _Offer) -> schemas.Offer:
    return schemas.Offer.from_price(offer.price, round(offer.distance_km, DISTANCE_DECIMALS))


def _resolve_item(
    item: schemas.GroceryItemInput,
    candidates: _ItemCandidates,
    offers_by_product: Mapping[int, Sequence[_Offer]],
    filters: schemas.SearchFilters,
    excluded: set[str],
) -> tuple[schemas.ItemResult, _Offer | None]:
    brand_matched: bool | None = None
    offers: list[_Offer] = []
    if candidates.brand_products is not None:
        offers = _ranked_offers(candidates.brand_products, offers_by_product, filters, excluded)
        brand_matched = bool(offers)
    if not offers:
        # No brand requested, or the brand is not offered nearby: any brand will do.
        offers = _ranked_offers(candidates.products, offers_by_product, filters, excluded)

    picked = _distinct(offers, 1 + MAX_ALTERNATIVES)
    best = picked[0] if picked else None
    message_key: schemas.SearchMessageKey | None = None
    if best is None:
        message_key = "search.no_match"
    elif brand_matched is False:
        message_key = "search.brand_not_found"
    result = schemas.ItemResult(
        query=item,
        matched=best is not None,
        brand_matched=brand_matched,
        best=None if best is None else _to_schema(best),
        alternatives=[_to_schema(offer) for offer in picked[1:]],
        line_total=None if best is None else round(best.price.price * item.quantity, 2),
        message_key=message_key,
    )
    return result, best


def _load_offers(
    db: Session, product_ids: set[int], nearby: Mapping[int, tuple[Store, float]]
) -> dict[int, list[_Offer]]:
    """Prices of the candidate products in the nearby stores, grouped by product id."""
    offers: dict[int, list[_Offer]] = {}
    if not product_ids or not nearby:
        return offers
    prices = db.scalars(
        select(Price).where(
            Price.product_id.in_(sorted(product_ids)), Price.store_id.in_(sorted(nearby))
        )
    )
    for price in prices:
        offers.setdefault(price.product_id, []).append(_Offer(price, nearby[price.store_id][1]))
    return offers


def default_list_name(language: schemas.Language, moment: datetime) -> str:
    """Dated name of a list saved without one, e.g. "Liste du 2 novembre 2026"."""
    if language == "en":
        return f"List of {_MONTHS_EN[moment.month - 1]} {moment.day}, {moment.year}"
    day = "1er" if moment.day == 1 else str(moment.day)
    return f"Liste du {day} {_MONTHS_FR[moment.month - 1]} {moment.year}"


def _owned_list(db: Session, user: User, list_id: int) -> GroceryList:
    grocery_list = db.scalar(
        select(GroceryList).where(GroceryList.id == list_id, GroceryList.user_id == user.id)
    )
    if grocery_list is None:
        raise ListNotFoundError(list_id)
    return grocery_list


def _save_to_history(
    db: Session, user: User, request: schemas.SearchRequest, existing: GroceryList | None
) -> GroceryList:
    """Replace the items of ``existing`` (and touch it), or create a new history entry."""
    now = utcnow()
    items = [item.model_dump() for item in request.items]
    if existing is not None:
        existing.items = items
        existing.last_used_at = now
        if request.list_name is not None:
            existing.name = request.list_name
        return existing
    grocery_list = GroceryList(
        user_id=user.id,
        name=request.list_name or default_list_name(user.language, now),
        items=items,
        bookmarked=False,
        created_at=now,
        last_used_at=now,
    )
    db.add(grocery_list)
    return grocery_list


def search_grocery_list(
    db: Session, user: User, request: schemas.SearchRequest, *, settings: Settings
) -> schemas.SearchResponse:
    """Resolve every item of the list and optionally save it to the user's history.

    Raises ``ListNotFoundError`` when ``list_id`` is not a list of ``user`` (checked first, and
    only when the list is to be saved) and ``stores.StoresUnavailableError`` when the area
    cannot be discovered.
    """
    existing = None
    if request.save_to_history and request.list_id is not None:
        existing = _owned_list(db, user, request.list_id)

    radius_km = resolve_radius_km(request.radius_km, user.search_radius_km, settings)
    ensure_area(db, request.lat, request.lon, radius_km, settings=settings)
    nearby = {
        store.id: (store, distance)
        for store, distance in stores_near(db, request.lat, request.lon, radius_km)
    }

    index = ProductIndex(db.scalars(select(Product).order_by(Product.id)))
    filters = request.filters
    candidates = [_item_candidates(index, item, filters) for item in request.items]
    product_ids = {
        product.id
        for item_candidates in candidates
        for product in (*item_candidates.products, *(item_candidates.brand_products or ()))
    }
    offers_by_product = _load_offers(db, product_ids, nearby)
    excluded = {normalise_text(chain) for chain in filters.exclude_chains}

    results: list[schemas.ItemResult] = []
    best_offers: list[_Offer] = []
    for item, item_candidates in zip(request.items, candidates, strict=True):
        result, best = _resolve_item(item, item_candidates, offers_by_product, filters, excluded)
        results.append(result)
        if best is not None:
            best_offers.append(best)

    best_stores = {offer.price.store_id: offer for offer in best_offers}
    stores = [
        schemas.Store.from_model(offer.price.store, round(offer.distance_km, DISTANCE_DECIMALS))
        for offer in sorted(
            best_stores.values(), key=lambda offer: (offer.distance_km, offer.price.store_id)
        )
    ]

    list_id: int | None = None
    if request.save_to_history:
        grocery_list = _save_to_history(db, user, request, existing)
        db.commit()
        list_id = grocery_list.id

    return schemas.SearchResponse(
        list_id=list_id,
        prices_are_demo=get_price_source(settings.price_source).is_demo,
        results=results,
        stores=stores,
        best_total=round(sum(result.line_total or 0.0 for result in results), 2),
    )
