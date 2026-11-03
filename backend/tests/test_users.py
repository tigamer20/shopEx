"""Current-user profile endpoints (``/users/me``) and access-token handling."""

from __future__ import annotations

import secrets
from datetime import timedelta
from typing import Any

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import Settings
from app.models import GroceryList, User
from app.security import JWT_ALGORITHM, create_access_token

ME_URL = "/api/v1/users/me"
LOGIN_URL = "/api/v1/auth/login"
LISTS_URL = "/api/v1/lists"
REGISTER_URL = "/api/v1/auth/register"


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _register(client: TestClient, email: str) -> dict[str, Any]:
    response = client.post(
        REGISTER_URL,
        json={"email": email, "password": secrets.token_urlsafe(16), "display_name": "Someone"},
    )
    assert response.status_code == 201
    return dict(response.json())


# --------------------------------------------------------------------------------------------
# GET /users/me
# --------------------------------------------------------------------------------------------


def test_get_me_returns_the_profile(
    client: TestClient, user: User, auth_headers: dict[str, str]
) -> None:
    response = client.get(ME_URL, headers=auth_headers)

    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == user.id
    assert payload["email"] == user.email
    assert payload["display_name"] == "Test User"
    assert payload["language"] == "fr"
    assert payload["search_radius_km"] == 10
    assert payload["travel_mode"] == "driving"
    assert payload["tutorial_completed"] is False
    assert payload["created_at"]
    assert "password_hash" not in payload


@pytest.mark.parametrize(
    ("method", "body"),
    [("GET", None), ("PATCH", {"language": "en"}), ("DELETE", None)],
)
def test_me_requires_authentication(
    client: TestClient, user: User, method: str, body: dict[str, Any] | None
) -> None:
    response = client.request(method, ME_URL, json=body)

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


@pytest.mark.parametrize(
    "authorization",
    [
        "Bearer not-a-jwt",
        "Bearer ",
        "Basic dXNlcjpwYXNz",
        "Token abc",
    ],
)
def test_malformed_authorization_gets_401(
    client: TestClient, user: User, authorization: str
) -> None:
    response = client.get(ME_URL, headers={"Authorization": authorization})

    assert response.status_code == 401


def test_expired_token_gets_401(client: TestClient, user: User, settings: Settings) -> None:
    token = create_access_token(user.id, settings=settings, expires_delta=timedelta(seconds=-5))

    response = client.get(ME_URL, headers=_bearer(token))

    assert response.status_code == 401


def test_token_signed_with_another_secret_gets_401(client: TestClient, user: User) -> None:
    forged = jwt.encode(
        {"sub": str(user.id), "iat": 0, "exp": 4_102_444_800},
        secrets.token_urlsafe(48),
        algorithm=JWT_ALGORITHM,
    )

    response = client.get(ME_URL, headers=_bearer(forged))

    assert response.status_code == 401


def test_unsigned_token_gets_401(client: TestClient, user: User) -> None:
    unsigned = jwt.encode(
        {"sub": str(user.id), "iat": 0, "exp": 4_102_444_800}, key=None, algorithm="none"
    )

    response = client.get(ME_URL, headers=_bearer(unsigned))

    assert response.status_code == 401


def test_token_of_unknown_user_gets_401(client: TestClient, settings: Settings) -> None:
    response = client.get(ME_URL, headers=_bearer(create_access_token(999_999, settings=settings)))

    assert response.status_code == 401


# --------------------------------------------------------------------------------------------
# PATCH /users/me
# --------------------------------------------------------------------------------------------


def test_patch_me_updates_every_preference(
    client: TestClient, db: Session, user: User, auth_headers: dict[str, str]
) -> None:
    changes = {
        "display_name": "  Dominique  ",
        "language": "en",
        "search_radius_km": 25.5,
        "travel_mode": "cycling",
        "tutorial_completed": True,
    }

    response = client.patch(ME_URL, json=changes, headers=auth_headers)

    assert response.status_code == 200
    payload = response.json()
    assert payload["display_name"] == "Dominique"
    assert payload["language"] == "en"
    assert payload["search_radius_km"] == 25.5
    assert payload["travel_mode"] == "cycling"
    assert payload["tutorial_completed"] is True
    db.expire_all()
    stored = db.get(User, user.id)
    assert stored is not None
    assert (stored.display_name, stored.language, stored.travel_mode) == (
        "Dominique",
        "en",
        "cycling",
    )
    assert client.get(ME_URL, headers=auth_headers).json() == payload


def test_patch_me_leaves_omitted_and_null_fields_untouched(
    client: TestClient, user: User, auth_headers: dict[str, str]
) -> None:
    response = client.patch(
        ME_URL, json={"language": "en", "display_name": None}, headers=auth_headers
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["language"] == "en"
    assert payload["display_name"] == "Test User"
    assert payload["travel_mode"] == "driving"


def test_patch_me_with_an_empty_body_changes_nothing(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    before = client.get(ME_URL, headers=auth_headers).json()

    response = client.patch(ME_URL, json={}, headers=auth_headers)

    assert response.status_code == 200
    assert response.json() == before


@pytest.mark.parametrize(
    "body",
    [
        {"display_name": ""},
        {"display_name": "x" * 61},
        {"language": "de"},
        {"search_radius_km": 0.5},
        {"search_radius_km": 50.1},
        {"search_radius_km": "far"},
        {"travel_mode": "flying"},
        {"tutorial_completed": "maybe"},
        # Identity and credentials are not editable through this endpoint.
        {"email": "new@example.com"},
        {"password": "new-password-123"},
        {"id": 1},
    ],
)
def test_patch_me_validates_the_body(
    client: TestClient, db: Session, user: User, auth_headers: dict[str, str], body: dict[str, Any]
) -> None:
    original = (user.email, user.display_name, user.password_hash)

    response = client.patch(ME_URL, json=body, headers=auth_headers)

    assert response.status_code == 422
    db.expire_all()
    stored = db.get(User, user.id)
    assert stored is not None
    assert (stored.email, stored.display_name, stored.password_hash) == original


def test_patch_me_accepts_the_radius_bounds(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    for radius in (1, 50):
        response = client.patch(ME_URL, json={"search_radius_km": radius}, headers=auth_headers)

        assert response.status_code == 200
        assert response.json()["search_radius_km"] == radius


# --------------------------------------------------------------------------------------------
# DELETE /users/me
# --------------------------------------------------------------------------------------------


def _create_list(client: TestClient, headers: dict[str, str], name: str) -> int:
    response = client.post(
        LISTS_URL, json={"name": name, "items": [{"name": "milk"}]}, headers=headers
    )
    assert response.status_code == 201
    return int(response.json()["id"])


def test_delete_me_removes_the_account_and_its_lists(
    client: TestClient,
    db: Session,
    user: User,
    user_password: str,
    auth_headers: dict[str, str],
) -> None:
    user_id, email = user.id, user.email
    _create_list(client, auth_headers, "Weekly")
    _create_list(client, auth_headers, "Party")

    response = client.delete(ME_URL, headers=auth_headers)

    assert response.status_code == 204
    assert response.content == b""
    db.expire_all()
    assert db.get(User, user_id) is None
    remaining = db.scalar(
        select(func.count()).select_from(GroceryList).where(GroceryList.user_id == user_id)
    )
    assert remaining == 0
    # The old token no longer works and the credentials are gone.
    assert client.get(ME_URL, headers=auth_headers).status_code == 401
    login = client.post(LOGIN_URL, json={"email": email, "password": user_password})
    assert login.status_code == 401


def test_delete_me_keeps_other_accounts_and_their_lists(
    client: TestClient, db: Session, auth_headers: dict[str, str]
) -> None:
    registered = _register(client, f"other-{secrets.token_hex(4)}@example.com")
    other_headers = _bearer(registered["access_token"])
    other_list_id = _create_list(client, other_headers, "Other's list")

    assert client.delete(ME_URL, headers=auth_headers).status_code == 204

    assert client.get(ME_URL, headers=other_headers).status_code == 200
    assert client.get(f"{LISTS_URL}/{other_list_id}", headers=other_headers).status_code == 200


def test_email_of_a_deleted_account_can_register_again(
    client: TestClient, user: User, auth_headers: dict[str, str]
) -> None:
    email = user.email
    assert client.delete(ME_URL, headers=auth_headers).status_code == 204

    registered = _register(client, email)

    assert registered["user"]["email"] == email


def test_token_of_a_deleted_account_never_opens_a_newer_account(client: TestClient) -> None:
    # Regression: SQLite reuses the highest rowid after a delete unless AUTOINCREMENT is set,
    # which would let the old token (subject = user id) sign in as the next account.
    first = _register(client, f"first-{secrets.token_hex(4)}@example.com")
    old_headers = _bearer(first["access_token"])
    assert client.delete(ME_URL, headers=old_headers).status_code == 204

    second = _register(client, f"second-{secrets.token_hex(4)}@example.com")

    assert second["user"]["id"] != first["user"]["id"]
    assert client.get(ME_URL, headers=old_headers).status_code == 401
