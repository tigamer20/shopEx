"""``POST /api/v1/search``: the core flow end to end, with Overpass faked (no network)."""

from __future__ import annotations

import secrets
from datetime import timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import utcnow
from app.models import GroceryList, User
from app.security import hash_password

from .conftest import OutboundHttp
from .factories import HOME, install_overpass, three_shops

URL = "/api/v1/search"
ITEMS = [{"name": "lait", "quantity": 2}, {"name": "bananes", "brand": "Terre Vivace"}]


@pytest.fixture
def shops(outbound_http: OutboundHttp) -> None:
    install_overpass(outbound_http, three_shops())


def body(**extra: Any) -> dict[str, Any]:
    return {"lat": HOME[0], "lon": HOME[1], "radius_km": 5, "items": ITEMS, **extra}


def make_list(db: Session, owner: User, name: str = "Épicerie de la semaine") -> GroceryList:
    created = utcnow() - timedelta(days=3)
    grocery_list = GroceryList(
        user_id=owner.id,
        name=name,
        items=[{"name": "pain", "brand": None, "quantity": 1}],
        bookmarked=True,
        created_at=created,
        last_used_at=created,
    )
    db.add(grocery_list)
    db.commit()
    return grocery_list


def test_search_requires_authentication(client: TestClient) -> None:
    assert client.post(URL, json=body()).status_code == 401


@pytest.mark.usefixtures("shops")
def test_search_returns_results_and_saves_a_new_list(
    client: TestClient, auth_headers: dict[str, str], db: Session, user: User
) -> None:
    response = client.post(URL, json=body(), headers=auth_headers)

    assert response.status_code == 200
    payload = response.json()
    assert payload["prices_are_demo"] is True
    assert payload["currency"] == "CAD"
    milk, bananas = payload["results"]
    assert milk["query"] == {"name": "lait", "brand": None, "quantity": 2}
    assert milk["matched"] is True and milk["brand_matched"] is None
    assert milk["line_total"] == round(milk["best"]["price"] * 2, 2)
    assert len(milk["alternatives"]) == 2
    assert bananas["brand_matched"] is True
    assert bananas["best"]["product"]["brand"] == "Terre Vivace"
    assert payload["best_total"] == round(milk["line_total"] + bananas["line_total"], 2)
    assert payload["stores"]
    assert all(store["distance_km"] is not None for store in payload["stores"])

    saved = db.get(GroceryList, payload["list_id"])
    assert saved is not None
    assert saved.user_id == user.id
    assert saved.bookmarked is False
    assert saved.name.startswith("Liste du ")
    assert saved.items == [
        {"name": "lait", "brand": None, "quantity": 2},
        {"name": "bananes", "brand": "Terre Vivace", "quantity": 1},
    ]
    listed = client.get("/api/v1/lists", headers=auth_headers).json()
    assert [entry["id"] for entry in listed] == [saved.id]
    assert client.get(f"/api/v1/lists/{saved.id}", headers=auth_headers).status_code == 200


@pytest.mark.usefixtures("shops")
def test_search_names_the_new_list_as_asked_or_in_the_user_language(
    client: TestClient, auth_headers: dict[str, str], db: Session, user: User
) -> None:
    named = client.post(URL, json=body(list_name="  Souper du vendredi "), headers=auth_headers)
    user.language = "en"
    db.commit()
    dated = client.post(URL, json=body(), headers=auth_headers)

    named_list = db.get(GroceryList, named.json()["list_id"])
    dated_list = db.get(GroceryList, dated.json()["list_id"])
    assert named_list is not None and named_list.name == "Souper du vendredi"
    assert dated_list is not None and dated_list.name.startswith("List of ")


@pytest.mark.usefixtures("shops")
def test_search_updates_the_given_list(
    client: TestClient, auth_headers: dict[str, str], db: Session, user: User
) -> None:
    grocery_list = make_list(db, user)
    created_at, last_used_at = grocery_list.created_at, grocery_list.last_used_at

    response = client.post(URL, json=body(list_id=grocery_list.id), headers=auth_headers)

    assert response.status_code == 200
    assert response.json()["list_id"] == grocery_list.id
    db.expire_all()
    updated = db.get(GroceryList, grocery_list.id)
    assert updated is not None
    assert updated.items[0] == {"name": "lait", "brand": None, "quantity": 2}
    assert updated.name == "Épicerie de la semaine"
    assert updated.bookmarked is True
    assert updated.created_at == created_at
    assert updated.last_used_at > last_used_at
    assert len(list(db.scalars(select(GroceryList)))) == 1


@pytest.mark.usefixtures("shops")
def test_search_can_rename_the_given_list(
    client: TestClient, auth_headers: dict[str, str], db: Session, user: User
) -> None:
    grocery_list = make_list(db, user)

    client.post(
        URL, json=body(list_id=grocery_list.id, list_name="Nouveau nom"), headers=auth_headers
    )

    db.expire_all()
    renamed = db.get(GroceryList, grocery_list.id)
    assert renamed is not None and renamed.name == "Nouveau nom"


@pytest.mark.usefixtures("shops")
def test_search_cannot_write_into_another_users_list(
    client: TestClient, auth_headers: dict[str, str], db: Session
) -> None:
    other = User(
        email=f"other-{secrets.token_hex(4)}@example.com",
        password_hash=hash_password(secrets.token_urlsafe(16)),
        display_name="Autre",
    )
    db.add(other)
    db.commit()
    foreign = make_list(db, other)

    response = client.post(URL, json=body(list_id=foreign.id), headers=auth_headers)
    missing = client.post(URL, json=body(list_id=987654), headers=auth_headers)

    assert response.status_code == 404
    assert response.json() == {"detail": "List not found"}
    assert missing.status_code == 404
    db.expire_all()
    untouched = db.get(GroceryList, foreign.id)
    assert untouched is not None and untouched.items == [
        {"name": "pain", "brand": None, "quantity": 1}
    ]


@pytest.mark.usefixtures("shops")
def test_search_without_history_saves_nothing(
    client: TestClient, auth_headers: dict[str, str], db: Session
) -> None:
    response = client.post(URL, json=body(save_to_history=False), headers=auth_headers)

    assert response.status_code == 200
    assert response.json()["list_id"] is None
    assert db.scalar(select(GroceryList)) is None


def test_search_falls_back_to_demo_stores_when_overpass_is_down(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    response = client.post(URL, json=body(save_to_history=False), headers=auth_headers)

    assert response.status_code == 200
    stores = response.json()["stores"]
    assert stores and {store["source"] for store in stores} == {"demo"}


def test_search_answers_503_when_stores_are_unavailable(
    client: TestClient, auth_headers: dict[str, str], monkeypatch: pytest.MonkeyPatch, db: Session
) -> None:
    monkeypatch.setenv("DEMO_STORES_FALLBACK", "false")
    get_settings.cache_clear()

    response = client.post(URL, json=body(), headers=auth_headers)

    assert response.status_code == 503
    assert db.scalar(select(GroceryList)) is None


@pytest.mark.parametrize(
    "overrides",
    [
        {"items": []},
        {"items": [{"name": ""}]},
        {"items": [{"name": "lait", "quantity": 100}]},
        {"items": [{"name": "lait"}] * 101},
        {"lat": 100},
        {"radius_km": -1},
        {"filters": {"sort_by": "distance"}},
        {"filters": {"tags": ["spicy"]}},
        {"list_id": 0},
        {"unexpected": True},
    ],
)
def test_search_validates_the_request(
    client: TestClient, auth_headers: dict[str, str], overrides: dict[str, Any]
) -> None:
    assert client.post(URL, json=body(**overrides), headers=auth_headers).status_code == 422
