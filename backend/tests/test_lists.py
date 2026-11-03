"""Grocery list history and bookmarks (``/lists``)."""

from __future__ import annotations

import secrets
from datetime import timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import Settings
from app.db import utcnow
from app.models import GroceryList, User
from app.security import create_access_token, hash_password

LISTS_URL = "/api/v1/lists"

SUMMARY_FIELDS = {"id", "name", "items_count", "bookmarked", "created_at", "last_used_at"}
LIST_FIELDS = {"id", "name", "items", "bookmarked", "created_at", "last_used_at"}


def _list_url(list_id: int | str) -> str:
    return f"{LISTS_URL}/{list_id}"


def _new_list(**overrides: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "name": "Weekly groceries",
        "items": [{"name": "milk", "brand": "Ferme Soleil", "quantity": 2}, {"name": "bread"}],
    }
    body.update(overrides)
    return body


def _create(client: TestClient, headers: dict[str, str], **overrides: Any) -> dict[str, Any]:
    response = client.post(LISTS_URL, json=_new_list(**overrides), headers=headers)
    assert response.status_code == 201, response.text
    return dict(response.json())


def _count_lists(db: Session) -> int:
    return int(db.scalar(select(func.count()).select_from(GroceryList)) or 0)


@pytest.fixture
def other_headers(db: Session, settings: Settings) -> dict[str, str]:
    """Bearer header of a second, unrelated account."""
    other = User(
        email=f"other-{secrets.token_hex(4)}@example.com",
        password_hash=hash_password(secrets.token_urlsafe(16)),
        display_name="Other User",
    )
    db.add(other)
    db.commit()
    return {"Authorization": f"Bearer {create_access_token(other.id, settings=settings)}"}


# --------------------------------------------------------------------------------------------
# POST /lists
# --------------------------------------------------------------------------------------------


def test_create_list_returns_201_with_normalised_items(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    response = client.post(
        LISTS_URL,
        json={
            "name": "  Weekly groceries  ",
            "items": [
                {"name": "  milk ", "brand": " Ferme Soleil ", "quantity": 2},
                {"name": "bread", "brand": ""},
                {"name": "eggs", "brand": None},
            ],
        },
        headers=auth_headers,
    )

    assert response.status_code == 201
    payload = response.json()
    assert set(payload) == LIST_FIELDS
    assert payload["name"] == "Weekly groceries"
    assert payload["items"] == [
        {"name": "milk", "brand": "Ferme Soleil", "quantity": 2},
        {"name": "bread", "brand": None, "quantity": 1},
        {"name": "eggs", "brand": None, "quantity": 1},
    ]
    assert payload["bookmarked"] is False
    assert payload["created_at"] == payload["last_used_at"]


def test_create_list_stores_it_for_the_caller(
    client: TestClient, db: Session, user: User, auth_headers: dict[str, str]
) -> None:
    created = _create(client, auth_headers, bookmarked=True)

    stored = db.get(GroceryList, created["id"])
    assert stored is not None
    assert stored.user_id == user.id
    assert stored.bookmarked is True
    assert stored.items == [
        {"name": "milk", "brand": "Ferme Soleil", "quantity": 2},
        {"name": "bread", "brand": None, "quantity": 1},
    ]


def test_create_list_accepts_the_size_limits(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    items = [{"name": "x" * 100, "brand": "b" * 60, "quantity": 99}] * 100

    created = _create(client, auth_headers, name="n" * 80, items=items)

    assert len(created["items"]) == 100


@pytest.mark.parametrize(
    "overrides",
    [
        {"name": ""},
        {"name": "   "},
        {"name": "n" * 81},
        {"items": []},
        {"items": [{"name": "milk"}] * 101},
        {"items": [{"name": ""}]},
        {"items": [{"name": "x" * 101}]},
        {"items": [{"name": "milk", "brand": "b" * 61}]},
        {"items": [{"name": "milk", "quantity": 0}]},
        {"items": [{"name": "milk", "quantity": 100}]},
        {"items": [{"name": "milk", "quantity": "two"}]},
        {"items": [{"name": "milk", "price": 1.5}]},
        {"items": "milk"},
        {"bookmarked": "sometimes"},
        {"user_id": 1},
        {"id": 1},
    ],
)
def test_create_list_validates_the_body(
    client: TestClient, db: Session, auth_headers: dict[str, str], overrides: dict[str, Any]
) -> None:
    response = client.post(LISTS_URL, json=_new_list(**overrides), headers=auth_headers)

    assert response.status_code == 422
    assert _count_lists(db) == 0


def test_create_list_requires_name_and_items(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    assert client.post(LISTS_URL, json={"name": "x"}, headers=auth_headers).status_code == 422
    assert (
        client.post(LISTS_URL, json={"items": [{"name": "milk"}]}, headers=auth_headers).status_code
        == 422
    )


# --------------------------------------------------------------------------------------------
# GET /lists
# --------------------------------------------------------------------------------------------


def test_history_is_empty_for_a_new_user(client: TestClient, auth_headers: dict[str, str]) -> None:
    response = client.get(LISTS_URL, headers=auth_headers)

    assert response.status_code == 200
    assert response.json() == []


def test_history_returns_summaries_with_items_count(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    created = _create(client, auth_headers, items=[{"name": "milk"}] * 3)

    response = client.get(LISTS_URL, headers=auth_headers)

    assert response.status_code == 200
    [summary] = response.json()
    assert set(summary) == SUMMARY_FIELDS
    assert summary["id"] == created["id"]
    assert summary["name"] == created["name"]
    assert summary["items_count"] == 3
    assert summary["bookmarked"] is False
    assert summary["created_at"] == created["created_at"]
    assert summary["last_used_at"] == created["last_used_at"]


def test_history_is_ordered_by_last_used_at_desc(
    client: TestClient, db: Session, auth_headers: dict[str, str]
) -> None:
    ids = [_create(client, auth_headers, name=f"List {index}")["id"] for index in range(3)]
    now = utcnow()
    # Oldest first in creation order, but used in a different order.
    for list_id, days_ago in zip(ids, (3, 1, 2), strict=True):
        stored = db.get(GroceryList, list_id)
        assert stored is not None
        stored.last_used_at = now - timedelta(days=days_ago)
    db.commit()

    response = client.get(LISTS_URL, headers=auth_headers)

    assert [summary["id"] for summary in response.json()] == [ids[1], ids[2], ids[0]]


def test_history_breaks_timestamp_ties_by_newest_id(
    client: TestClient, db: Session, auth_headers: dict[str, str]
) -> None:
    ids = [_create(client, auth_headers, name=f"List {index}")["id"] for index in range(3)]
    same_time = utcnow()
    for list_id in ids:
        stored = db.get(GroceryList, list_id)
        assert stored is not None
        stored.last_used_at = same_time
    db.commit()

    response = client.get(LISTS_URL, headers=auth_headers)

    assert [summary["id"] for summary in response.json()] == list(reversed(ids))


def test_bookmarked_filter(client: TestClient, auth_headers: dict[str, str]) -> None:
    plain = _create(client, auth_headers, name="Plain")
    bookmark = _create(client, auth_headers, name="Bookmark", bookmarked=True)

    everything = client.get(LISTS_URL, headers=auth_headers).json()
    bookmarks = client.get(LISTS_URL, params={"bookmarked": "true"}, headers=auth_headers).json()
    others = client.get(LISTS_URL, params={"bookmarked": "false"}, headers=auth_headers).json()

    assert {summary["id"] for summary in everything} == {plain["id"], bookmark["id"]}
    assert [summary["id"] for summary in bookmarks] == [bookmark["id"]]
    assert [summary["id"] for summary in others] == [plain["id"]]


def test_bookmarked_filter_rejects_non_booleans(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    response = client.get(LISTS_URL, params={"bookmarked": "maybe"}, headers=auth_headers)

    assert response.status_code == 422


# --------------------------------------------------------------------------------------------
# GET / PATCH / DELETE /lists/{id}
# --------------------------------------------------------------------------------------------


def test_get_list_returns_the_full_list(client: TestClient, auth_headers: dict[str, str]) -> None:
    created = _create(client, auth_headers)

    response = client.get(_list_url(created["id"]), headers=auth_headers)

    assert response.status_code == 200
    assert response.json() == created


def test_patch_list_updates_name_items_and_bookmark(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    created = _create(client, auth_headers)

    response = client.patch(
        _list_url(created["id"]),
        json={
            "name": " Party ",
            "items": [{"name": "chips", "quantity": 3}],
            "bookmarked": True,
        },
        headers=auth_headers,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["name"] == "Party"
    assert payload["items"] == [{"name": "chips", "brand": None, "quantity": 3}]
    assert payload["bookmarked"] is True
    # Editing is not "using": the list keeps its place in the history.
    assert payload["created_at"] == created["created_at"]
    assert payload["last_used_at"] == created["last_used_at"]
    assert client.get(_list_url(created["id"]), headers=auth_headers).json() == payload


def test_patch_list_leaves_omitted_and_null_fields_untouched(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    created = _create(client, auth_headers)

    response = client.patch(
        _list_url(created["id"]),
        json={"bookmarked": True, "name": None, "items": None},
        headers=auth_headers,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["bookmarked"] is True
    assert payload["name"] == created["name"]
    assert payload["items"] == created["items"]


def test_patch_list_rename_keeps_items_and_bookmark(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    created = _create(client, auth_headers, bookmarked=True)

    response = client.patch(
        _list_url(created["id"]), json={"name": "Renamed"}, headers=auth_headers
    )

    assert response.status_code == 200
    assert response.json() == {**created, "name": "Renamed"}


def test_patch_list_can_remove_a_bookmark(client: TestClient, auth_headers: dict[str, str]) -> None:
    created = _create(client, auth_headers, bookmarked=True)

    response = client.patch(
        _list_url(created["id"]), json={"bookmarked": False}, headers=auth_headers
    )

    assert response.json()["bookmarked"] is False


@pytest.mark.parametrize(
    "body",
    [
        {"name": ""},
        {"name": "n" * 81},
        {"items": []},
        {"items": [{"name": "milk", "quantity": 0}]},
        {"bookmarked": "sometimes"},
        {"user_id": 999},
        {"created_at": "2020-01-01T00:00:00Z"},
    ],
)
def test_patch_list_validates_the_body(
    client: TestClient, auth_headers: dict[str, str], body: dict[str, Any]
) -> None:
    created = _create(client, auth_headers)

    response = client.patch(_list_url(created["id"]), json=body, headers=auth_headers)

    assert response.status_code == 422
    assert client.get(_list_url(created["id"]), headers=auth_headers).json() == created


def test_delete_list_returns_204_and_removes_only_that_list(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    doomed = _create(client, auth_headers, name="Doomed")
    kept = _create(client, auth_headers, name="Kept")

    response = client.delete(_list_url(doomed["id"]), headers=auth_headers)

    assert response.status_code == 204
    assert response.content == b""
    assert client.get(_list_url(doomed["id"]), headers=auth_headers).status_code == 404
    remaining = client.get(LISTS_URL, headers=auth_headers).json()
    assert [summary["id"] for summary in remaining] == [kept["id"]]


def test_unknown_list_is_404(client: TestClient, auth_headers: dict[str, str]) -> None:
    for method in ("GET", "PATCH", "DELETE"):
        body = {"bookmarked": True} if method == "PATCH" else None
        response = client.request(method, _list_url(424242), json=body, headers=auth_headers)

        assert response.status_code == 404
        assert response.json() == {"detail": "List not found"}


@pytest.mark.parametrize("list_id", ["0", "-1", "abc", "1.5", str(2**31), str(10**30)])
def test_invalid_list_id_is_422(
    client: TestClient, auth_headers: dict[str, str], list_id: str
) -> None:
    response = client.get(_list_url(list_id), headers=auth_headers)

    assert response.status_code == 422


# --------------------------------------------------------------------------------------------
# Ownership & authentication
# --------------------------------------------------------------------------------------------


def test_lists_of_another_user_are_invisible(
    client: TestClient, auth_headers: dict[str, str], other_headers: dict[str, str]
) -> None:
    mine = _create(client, auth_headers, name="Mine", bookmarked=True)
    theirs = _create(client, other_headers, name="Theirs", bookmarked=True)

    my_history = client.get(LISTS_URL, headers=auth_headers).json()
    my_bookmarks = client.get(LISTS_URL, params={"bookmarked": "true"}, headers=auth_headers)

    assert [summary["id"] for summary in my_history] == [mine["id"]]
    assert [summary["id"] for summary in my_bookmarks.json()] == [mine["id"]]
    assert theirs["id"] not in {summary["id"] for summary in my_history}


def test_another_users_list_answers_404_and_stays_unchanged(
    client: TestClient, auth_headers: dict[str, str], other_headers: dict[str, str]
) -> None:
    theirs = _create(client, other_headers, name="Theirs")
    url = _list_url(theirs["id"])

    read = client.get(url, headers=auth_headers)
    update = client.patch(url, json={"name": "Hijacked", "bookmarked": True}, headers=auth_headers)
    delete = client.delete(url, headers=auth_headers)

    for response in (read, update, delete):
        # Same answer as a list that does not exist: ids of other accounts cannot be probed.
        assert response.status_code == 404
        assert response.json() == {"detail": "List not found"}
    assert client.get(url, headers=other_headers).json() == theirs


@pytest.mark.parametrize(
    ("method", "path", "body"),
    [
        ("GET", LISTS_URL, None),
        ("POST", LISTS_URL, _new_list()),
        ("GET", _list_url(1), None),
        ("PATCH", _list_url(1), {"bookmarked": True}),
        ("DELETE", _list_url(1), None),
    ],
)
def test_lists_require_authentication(
    client: TestClient,
    db: Session,
    auth_headers: dict[str, str],
    method: str,
    path: str,
    body: dict[str, Any] | None,
) -> None:
    created = _create(client, auth_headers)
    assert created["id"] == 1

    response = client.request(method, path, json=body)

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    assert _count_lists(db) == 1
    assert client.get(_list_url(1), headers=auth_headers).json() == created
