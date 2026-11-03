"""Pydantic request/response models: the shared HTTP contract (ARCHITECTURE.md section 4).

Class names match the TypeScript mirror in ``client/src/api/types.ts``; field names are
snake_case on both sides. Several names (``User``, ``Store``...) also exist as ORM models, so
import this module as a namespace: ``from app import schemas`` then ``schemas.User``.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Annotated, Any, Literal, Self

from pydantic import (
    AfterValidator,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    EmailStr,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

if TYPE_CHECKING:
    from app import models

# --------------------------------------------------------------------------------------------
# Shared enumerations
# --------------------------------------------------------------------------------------------

Language = Literal["fr", "en"]
TravelMode = Literal["driving", "walking", "cycling"]
SortBy = Literal["price", "unit_price", "distance"]
SearchSortBy = Literal["price", "unit_price"]
DietaryTag = Literal[
    "organic", "gluten_free", "vegan", "vegetarian", "lactose_free", "local", "store_brand"
]
StoreSource = Literal["osm", "demo"]
PriceTier = Literal["discount", "standard", "premium"]
SizeUnit = Literal["g", "kg", "ml", "L", "unit"]
UnitPriceUnit = Literal["kg", "L", "unit"]
RoutingSource = Literal["osrm", "estimate"]
SearchMessageKey = Literal["search.no_match", "search.brand_not_found"]
Currency = Literal["CAD"]

# --------------------------------------------------------------------------------------------
# Reusable field types
# --------------------------------------------------------------------------------------------


def _trimmed(min_length: int, max_length: int) -> StringConstraints:
    """Constraint for text that is trimmed, then length-checked."""
    return StringConstraints(strip_whitespace=True, min_length=min_length, max_length=max_length)


def _split_comma_list(value: Any) -> Any:
    """Accept ``"a,b"`` as well as ``["a", "b"]`` or ``["a,b"]`` (repeated query params)."""
    if value is None:
        return None
    raw_items = [value] if isinstance(value, str) else value
    if not isinstance(raw_items, list | tuple):
        return value
    parts = (part.strip() for item in raw_items for part in str(item).split(","))
    return [part for part in parts if part]


# email-validator enforces the RFC length limits; addresses are stored lower-case.
Email = Annotated[EmailStr, AfterValidator(str.lower)]
# Passwords are never trimmed: every character counts.
Password = Annotated[str, StringConstraints(min_length=8, max_length=128)]
DisplayName = Annotated[str, _trimmed(1, 60)]
ListName = Annotated[str, _trimmed(1, 80)]
ItemName = Annotated[str, _trimmed(1, 100)]
BrandName = Annotated[str, _trimmed(0, 60)]
BrandFilter = Annotated[str, _trimmed(1, 60)]
ChainName = Annotated[str, _trimmed(1, 200)]
SectionId = Annotated[str, _trimmed(1, 40)]
SearchText = Annotated[str, _trimmed(1, 100)]
Latitude = Annotated[float, Field(ge=-90, le=90)]
Longitude = Annotated[float, Field(ge=-180, le=180)]
# Upper bound is MAX_RADIUS_KM (configurable): services clamp with min(radius, max_radius_km).
RadiusKm = Annotated[float, Field(gt=0)]
SearchRadiusKm = Annotated[float, Field(ge=1, le=50)]
NonNegativePrice = Annotated[float, Field(ge=0)]
# Ids are 32-bit INTEGER columns: larger values can never exist and would overflow drivers.
MAX_ID = 2**31 - 1
Id = Annotated[int, Field(ge=1, le=MAX_ID)]
TagList = Annotated[list[DietaryTag], BeforeValidator(_split_comma_list)]

# --------------------------------------------------------------------------------------------
# Base classes
# --------------------------------------------------------------------------------------------


class RequestModel(BaseModel):
    """JSON request body: unknown fields are rejected, non-finite numbers too."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class QueryModel(BaseModel):
    """Query-string parameters: unknown parameters are ignored (cache busters, tracking...)."""

    model_config = ConfigDict(extra="ignore", allow_inf_nan=False)


class PatchModel(RequestModel):
    """Partial update: only fields sent with a non-null value are applied."""

    def changes(self) -> dict[str, Any]:
        return self.model_dump(exclude_unset=True, exclude_none=True)


class ResponseModel(BaseModel):
    """Response payload, buildable from ORM objects with ``model_validate(obj)``."""

    model_config = ConfigDict(from_attributes=True)


# --------------------------------------------------------------------------------------------
# Auth & user
# --------------------------------------------------------------------------------------------


class RegisterRequest(RequestModel):
    email: Email
    password: Password
    display_name: DisplayName
    language: Language = "fr"


class LoginRequest(RequestModel):
    email: Email
    # No minimum here: the login answer must not reveal the password policy.
    password: Annotated[str, StringConstraints(min_length=1, max_length=128)]


class User(ResponseModel):
    id: int
    email: str
    display_name: str
    language: Language
    search_radius_km: float
    travel_mode: TravelMode
    tutorial_completed: bool
    created_at: datetime


class TokenResponse(ResponseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"  # noqa: S105 (OAuth token type, not a secret)
    user: User


class UserUpdate(PatchModel):
    display_name: DisplayName | None = None
    language: Language | None = None
    search_radius_km: SearchRadiusKm | None = None
    travel_mode: TravelMode | None = None
    tutorial_completed: bool | None = None


# --------------------------------------------------------------------------------------------
# Grocery lists (history & bookmarks)
# --------------------------------------------------------------------------------------------


class GroceryItemInput(BaseModel):
    """One line of a grocery list. Also stored as-is in ``GroceryList.items`` (JSON)."""

    model_config = ConfigDict(extra="forbid")

    name: ItemName
    brand: BrandName | None = None
    quantity: Annotated[int, Field(ge=1, le=99)] = 1

    @field_validator("brand")
    @classmethod
    def _blank_brand_is_none(cls, value: str | None) -> str | None:
        return value or None


GroceryItems = Annotated[list[GroceryItemInput], Field(min_length=1, max_length=100)]


class GroceryListCreate(RequestModel):
    name: ListName
    items: GroceryItems
    bookmarked: bool = False


class GroceryListUpdate(PatchModel):
    name: ListName | None = None
    items: GroceryItems | None = None
    bookmarked: bool | None = None


class GroceryList(ResponseModel):
    id: int
    name: str
    items: list[GroceryItemInput]
    bookmarked: bool
    created_at: datetime
    last_used_at: datetime


class GroceryListSummary(ResponseModel):
    id: int
    name: str
    items_count: int
    bookmarked: bool
    created_at: datetime
    last_used_at: datetime

    @model_validator(mode="before")
    @classmethod
    def _from_grocery_list(cls, data: Any) -> Any:
        """Allow ``GroceryListSummary.model_validate(orm_grocery_list)``."""
        if isinstance(data, dict) or not hasattr(data, "items"):
            return data
        return {
            "id": data.id,
            "name": data.name,
            "items_count": len(data.items),
            "bookmarked": data.bookmarked,
            "created_at": data.created_at,
            "last_used_at": data.last_used_at,
        }


# --------------------------------------------------------------------------------------------
# Stores & catalog
# --------------------------------------------------------------------------------------------


class Store(ResponseModel):
    id: int
    name: str
    chain: str | None
    address: str | None
    lat: float
    lon: float
    distance_km: float | None = None
    source: StoreSource
    price_tier: PriceTier

    @classmethod
    def from_model(cls, store: models.Store, distance_km: float | None = None) -> Self:
        return cls.model_validate(store).model_copy(update={"distance_km": distance_km})


class Section(ResponseModel):
    id: str
    name_fr: str
    name_en: str


class Product(ResponseModel):
    id: int
    slug: str
    name_fr: str
    name_en: str
    brand: str
    section_id: str
    size_value: float
    size_unit: SizeUnit
    tags: list[DietaryTag]


class Offer(ResponseModel):
    price_id: int
    product: Product
    store: Store
    price: float
    regular_price: float
    on_sale: bool
    unit_price: float
    unit_price_unit: UnitPriceUnit
    updated_at: datetime
    source: str

    @classmethod
    def from_price(cls, price: models.Price, distance_km: float | None = None) -> Self:
        """Build an offer from a ``Price`` row (with its product and store loaded)."""
        return cls(
            price_id=price.id,
            product=Product.model_validate(price.product),
            store=Store.from_model(price.store, distance_km),
            price=price.price,
            regular_price=price.regular_price,
            on_sale=price.on_sale,
            unit_price=price.unit_price,
            unit_price_unit=price.unit_price_unit,
            updated_at=price.updated_at,
            source=price.source,
        )


class OfferPage(ResponseModel):
    """Response of ``GET /catalog/offers``."""

    items: list[Offer]
    total: int
    prices_are_demo: bool


class StoresQuery(QueryModel):
    """Query of ``GET /stores``; ``radius_km`` defaults to the user's search radius."""

    lat: Latitude
    lon: Longitude
    radius_km: RadiusKm | None = None


class OffersQuery(QueryModel):
    """Query of ``GET /catalog/offers`` (``tags`` is a comma-separated list)."""

    lat: Latitude
    lon: Longitude
    radius_km: RadiusKm | None = None
    q: SearchText | None = None
    section: SectionId | None = None
    brand: BrandFilter | None = None
    chain: ChainName | None = None
    tags: TagList | None = None
    on_sale: bool | None = None
    min_price: NonNegativePrice | None = None
    max_price: NonNegativePrice | None = None
    store_id: Id | None = None
    sort: SortBy = "price"
    limit: Annotated[int, Field(ge=1, le=100)] = 30
    offset: Annotated[int, Field(ge=0)] = 0

    @model_validator(mode="after")
    def _check_price_range(self) -> Self:
        if (
            self.min_price is not None
            and self.max_price is not None
            and self.min_price > self.max_price
        ):
            raise ValueError("min_price must be less than or equal to max_price")
        return self


# --------------------------------------------------------------------------------------------
# Search (the core flow)
# --------------------------------------------------------------------------------------------


class SearchFilters(RequestModel):
    tags: TagList = Field(default_factory=list)
    on_sale_only: bool = False
    max_price: NonNegativePrice | None = None
    exclude_chains: Annotated[list[ChainName], Field(max_length=50)] = Field(default_factory=list)
    sort_by: SearchSortBy = "price"


class SearchRequest(RequestModel):
    lat: Latitude
    lon: Longitude
    radius_km: RadiusKm | None = None
    items: GroceryItems
    filters: SearchFilters = Field(default_factory=SearchFilters)
    save_to_history: bool = True
    list_name: ListName | None = None
    list_id: Id | None = None


class ItemResult(ResponseModel):
    query: GroceryItemInput
    matched: bool
    # None when no brand was requested; False when it was requested but not found.
    brand_matched: bool | None
    best: Offer | None
    alternatives: Annotated[list[Offer], Field(max_length=2)] = Field(default_factory=list)
    line_total: float | None
    message_key: SearchMessageKey | None = None


class SearchResponse(ResponseModel):
    list_id: int | None
    prices_are_demo: bool
    currency: Currency = "CAD"
    results: list[ItemResult]
    stores: list[Store]
    best_total: float


# --------------------------------------------------------------------------------------------
# Itinerary
# --------------------------------------------------------------------------------------------


class LatLon(RequestModel):
    lat: Latitude
    lon: Longitude


class ItineraryRequest(RequestModel):
    start: LatLon
    store_ids: Annotated[list[Id], Field(min_length=1, max_length=15)]
    # Defaults to the user's travel mode when omitted.
    travel_mode: TravelMode | None = None
    return_to_start: bool = False

    @field_validator("store_ids")
    @classmethod
    def _unique_store_ids(cls, value: list[int]) -> list[int]:
        if len(set(value)) != len(value):
            raise ValueError("store_ids must be unique")
        return value


class ItineraryStop(ResponseModel):
    order: Annotated[int, Field(ge=1)]
    store: Store
    leg_distance_km: float
    leg_duration_min: float
    arrival_min: float


class ItineraryResponse(ResponseModel):
    stops: list[ItineraryStop]
    total_distance_km: float
    total_duration_min: float
    # [lat, lon] pairs; None when no road geometry is available.
    geometry: list[tuple[float, float]] | None
    routing_source: RoutingSource
    maps_url: str


# --------------------------------------------------------------------------------------------
# Admin & health
# --------------------------------------------------------------------------------------------


class HealthResponse(ResponseModel):
    status: Literal["ok"] = "ok"
    version: str


class RefreshResult(ResponseModel):
    areas_refreshed: int
    stores_refreshed: int
    prices_updated: int
    started_at: datetime
    finished_at: datetime
