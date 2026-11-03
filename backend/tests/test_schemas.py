"""Validation rules of the shared request/response models."""

import secrets
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app import schemas
from app.models import GroceryList, Price, Product, Section, Store, User


def test_grocery_item_is_trimmed_and_blank_brand_becomes_none() -> None:
    item = schemas.GroceryItemInput(name="  Lait 2 %  ", brand="   ")

    assert item.name == "Lait 2 %"
    assert item.brand is None
    assert item.quantity == 1


@pytest.mark.parametrize(
    "payload",
    [
        {"name": ""},
        {"name": "x" * 101},
        {"name": "milk", "quantity": 0},
        {"name": "milk", "quantity": 100},
    ],
)
def test_grocery_item_bounds(payload: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        schemas.GroceryItemInput.model_validate(payload)


def test_register_lowercases_email_and_keeps_password_verbatim() -> None:
    password = f"  {secrets.token_urlsafe(12)}  "

    request = schemas.RegisterRequest(
        email="Jane.Doe@Example.com", password=password, display_name=" Jane "
    )

    assert request.email == "jane.doe@example.com"
    assert request.password == password
    assert request.display_name == "Jane"
    assert request.language == "fr"


@pytest.mark.parametrize(
    "overrides",
    [{"password": "short"}, {"email": "not-an-email"}, {"language": "de"}, {"role": "admin"}],
)
def test_register_rejects_invalid_input(overrides: dict[str, object]) -> None:
    payload = {"email": "a@example.com", "password": secrets.token_urlsafe(12), "display_name": "A"}

    with pytest.raises(ValidationError):
        schemas.RegisterRequest.model_validate({**payload, **overrides})


def test_user_update_changes_only_contains_sent_values() -> None:
    update = schemas.UserUpdate.model_validate({"language": "en", "display_name": None})

    assert update.changes() == {"language": "en"}


def test_user_update_radius_bounds() -> None:
    with pytest.raises(ValidationError):
        schemas.UserUpdate(search_radius_km=51)


def test_itinerary_request_rejects_duplicate_or_too_many_stores() -> None:
    start = {"lat": 45.5, "lon": -73.5}
    with pytest.raises(ValidationError, match="unique"):
        schemas.ItineraryRequest.model_validate({"start": start, "store_ids": [1, 1]})
    with pytest.raises(ValidationError):
        schemas.ItineraryRequest.model_validate({"start": start, "store_ids": list(range(1, 17))})


@pytest.mark.parametrize("bad_id", [0, schemas.MAX_ID + 1, 2**63])
def test_ids_must_fit_a_32_bit_column(bad_id: int) -> None:
    start = {"lat": 45.5, "lon": -73.5}
    with pytest.raises(ValidationError):
        schemas.ItineraryRequest.model_validate({"start": start, "store_ids": [bad_id]})
    with pytest.raises(ValidationError):
        schemas.OffersQuery.model_validate({"lat": 1, "lon": 2, "store_id": bad_id})
    with pytest.raises(ValidationError):
        schemas.SearchRequest.model_validate(
            {"lat": 1, "lon": 2, "items": [{"name": "milk"}], "list_id": bad_id}
        )

    assert schemas.OffersQuery(lat=1, lon=2, store_id=schemas.MAX_ID).store_id == schemas.MAX_ID


def test_search_request_defaults() -> None:
    request = schemas.SearchRequest.model_validate(
        {
            "lat": 45.5,
            "lon": -73.5,
            "items": [{"name": "milk"}],
            "filters": {"tags": "organic,vegan"},
        }
    )

    assert request.save_to_history is True
    assert request.filters.tags == ["organic", "vegan"]
    assert request.filters.sort_by == "price"


def test_offers_query_parses_tags_and_checks_price_range() -> None:
    query = schemas.OffersQuery.model_validate({"lat": 1, "lon": 2, "tags": "organic, local"})
    assert query.tags == ["organic", "local"]

    with pytest.raises(ValidationError, match="min_price"):
        schemas.OffersQuery.model_validate({"lat": 1, "lon": 2, "min_price": 5, "max_price": 1})


def test_non_finite_numbers_are_rejected() -> None:
    with pytest.raises(ValidationError):
        schemas.LatLon(lat=float("nan"), lon=0)
    with pytest.raises(ValidationError):
        schemas.StoresQuery(lat=0, lon=0, radius_km=float("inf"))


def test_response_models_build_from_orm_objects(db: Session, user: User) -> None:
    grocery_list = GroceryList(
        user_id=user.id, name="Week", items=[{"name": "milk", "quantity": 2}]
    )
    section = Section(id="dairy", name_fr="Produits laitiers", name_en="Dairy", sort_order=1)
    product = Product(
        slug="milk-2l",
        name_fr="Lait 2 %",
        name_en="2% milk",
        brand="Prairie Douce",
        section=section,
        size_value=2,
        size_unit="L",
        tags=["local"],
        keywords=["lait", "milk"],
    )
    store = Store(name="Demo Market", chain=None, address=None, lat=45.5, lon=-73.5, source="demo")
    price = Price(
        store=store,
        product=product,
        price=4.99,
        regular_price=5.49,
        on_sale=True,
        unit_price=2.5,
        unit_price_unit="L",
        source="demo",
    )
    db.add_all([grocery_list, price])
    db.commit()

    summary = schemas.GroceryListSummary.model_validate(grocery_list)
    offer = schemas.Offer.from_price(price, distance_km=1.2)

    assert summary.items_count == 1
    assert schemas.GroceryList.model_validate(grocery_list).items[0].quantity == 2
    assert schemas.User.model_validate(user).created_at.tzinfo == UTC
    assert offer.price_id == price.id
    assert offer.store.distance_km == 1.2
    assert offer.store.price_tier == "standard"
    assert offer.product.tags == ["local"]
    assert offer.updated_at <= datetime.now(UTC)
