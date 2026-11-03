"""Registration, login and the login rate limiter (``/auth``)."""

from __future__ import annotations

import secrets
from collections.abc import Iterator
from typing import Any, cast

import pytest
from argon2 import PasswordHasher
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import User
from app.routers.auth import get_login_rate_limiter
from app.security import LoginRateLimiter, password_needs_rehash, verify_password

REGISTER_URL = "/api/v1/auth/register"
LOGIN_URL = "/api/v1/auth/login"
ME_URL = "/api/v1/users/me"
BEARER = "bearer"  # noqa: S105 (OAuth token type, not a secret)


def _registration(**overrides: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "email": f"shopper-{secrets.token_hex(4)}@example.com",
        "password": secrets.token_urlsafe(16),
        "display_name": "Camille",
    }
    body.update(overrides)
    return body


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


class FakeClock:
    """Manually advanced monotonic clock for the rate limiter."""

    def __init__(self) -> None:
        self.now = 1_000.0

    def __call__(self) -> float:
        return self.now


@pytest.fixture
def clock(client: TestClient) -> Iterator[FakeClock]:
    """Install a limiter driven by a fake clock in the app under test."""
    fake_clock = FakeClock()
    limiter = LoginRateLimiter(max_failures=5, window_seconds=300, clock=fake_clock)
    app = cast(FastAPI, client.app)
    app.dependency_overrides[get_login_rate_limiter] = lambda: limiter
    yield fake_clock
    app.dependency_overrides.pop(get_login_rate_limiter, None)


# --------------------------------------------------------------------------------------------
# Register
# --------------------------------------------------------------------------------------------


def test_register_returns_201_with_a_working_token(client: TestClient) -> None:
    body = _registration(language="en")

    response = client.post(REGISTER_URL, json=body)

    assert response.status_code == 201
    payload = response.json()
    assert payload["token_type"] == BEARER
    assert set(payload["user"]) == {
        "id",
        "email",
        "display_name",
        "language",
        "search_radius_km",
        "travel_mode",
        "tutorial_completed",
        "created_at",
    }
    assert payload["user"]["email"] == body["email"]
    assert payload["user"]["display_name"] == "Camille"
    assert payload["user"]["language"] == "en"
    assert payload["user"]["search_radius_km"] == 10
    assert payload["user"]["travel_mode"] == "driving"
    assert payload["user"]["tutorial_completed"] is False

    me = client.get(ME_URL, headers=_bearer(payload["access_token"]))
    assert me.status_code == 200
    assert me.json() == payload["user"]


def test_register_defaults_to_french_and_normalises_input(client: TestClient) -> None:
    response = client.post(
        REGISTER_URL,
        json=_registration(email="Mixed.Case@Example.COM", display_name="  Camille  "),
    )

    assert response.status_code == 201
    user = response.json()["user"]
    assert user["email"] == "mixed.case@example.com"
    assert user["display_name"] == "Camille"
    assert user["language"] == "fr"


def test_register_stores_an_argon2_hash_not_the_password(client: TestClient, db: Session) -> None:
    body = _registration()

    response = client.post(REGISTER_URL, json=body)

    stored = db.get(User, response.json()["user"]["id"])
    assert stored is not None
    assert stored.password_hash != body["password"]
    assert stored.password_hash.startswith("$argon2id$")
    assert verify_password(body["password"], stored.password_hash)


@pytest.mark.parametrize("second_email", ["taken@example.com", "TAKEN@Example.com"])
def test_register_rejects_a_taken_email_case_insensitively(
    client: TestClient, db: Session, second_email: str
) -> None:
    assert (
        client.post(REGISTER_URL, json=_registration(email="taken@example.com")).status_code == 201
    )

    response = client.post(REGISTER_URL, json=_registration(email=second_email))

    assert response.status_code == 409
    assert response.json() == {"detail": "Email already registered"}
    assert len(db.scalars(select(User)).all()) == 1


def test_register_race_on_the_same_email_gets_409(
    client: TestClient, db: Session, user: User, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Simulate a concurrent registration: the pre-check sees no account, the unique index
    # then rejects the insert.
    monkeypatch.setattr(Session, "scalar", lambda *_args, **_kwargs: None)

    response = client.post(REGISTER_URL, json=_registration(email=user.email))

    assert response.status_code == 409
    assert response.json() == {"detail": "Email already registered"}
    monkeypatch.undo()
    assert len(db.scalars(select(User)).all()) == 1


@pytest.mark.parametrize(
    "overrides",
    [
        {"email": "not-an-email"},
        {"password": "short"},
        {"password": "x" * 129},
        {"display_name": ""},
        {"display_name": "   "},
        {"display_name": "x" * 61},
        {"language": "de"},
        {"is_admin": True},
    ],
)
def test_register_validates_the_body(
    client: TestClient, db: Session, overrides: dict[str, Any]
) -> None:
    response = client.post(REGISTER_URL, json=_registration(**overrides))

    assert response.status_code == 422
    assert db.scalars(select(User)).first() is None


def test_register_requires_every_mandatory_field(client: TestClient) -> None:
    response = client.post(REGISTER_URL, json={"email": "someone@example.com"})

    assert response.status_code == 422


# --------------------------------------------------------------------------------------------
# Login
# --------------------------------------------------------------------------------------------


def test_login_returns_a_token_for_valid_credentials(
    client: TestClient, user: User, user_password: str
) -> None:
    response = client.post(LOGIN_URL, json={"email": user.email, "password": user_password})

    assert response.status_code == 200
    payload = response.json()
    assert payload["token_type"] == BEARER
    assert payload["user"]["id"] == user.id
    me = client.get(ME_URL, headers=_bearer(payload["access_token"]))
    assert me.status_code == 200
    assert me.json()["id"] == user.id


def test_login_email_is_case_insensitive(
    client: TestClient, user: User, user_password: str
) -> None:
    response = client.post(LOGIN_URL, json={"email": user.email.upper(), "password": user_password})

    assert response.status_code == 200


def test_wrong_password_and_unknown_email_get_the_same_generic_401(
    client: TestClient, user: User, user_password: str
) -> None:
    wrong_password = client.post(
        LOGIN_URL, json={"email": user.email, "password": user_password + "x"}
    )
    unknown_email = client.post(
        LOGIN_URL, json={"email": "nobody@example.com", "password": user_password}
    )

    for response in (wrong_password, unknown_email):
        assert response.status_code == 401
        assert response.json() == {"detail": "Invalid credentials"}
        assert response.headers["www-authenticate"] == "Bearer"
        assert "access_token" not in response.text


def test_login_does_not_reveal_the_password_policy(client: TestClient, user: User) -> None:
    # A password shorter than the registration minimum is just wrong, not invalid input.
    response = client.post(LOGIN_URL, json={"email": user.email, "password": "x"})

    assert response.status_code == 401


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"email": "someone@example.com"},
        {"email": "not-an-email", "password": "whatever-password"},
        {"email": "someone@example.com", "password": ""},
        {"email": "someone@example.com", "password": "x" * 129},
        {"email": "someone@example.com", "password": "whatever-password", "extra": 1},
    ],
)
def test_login_validates_the_body(client: TestClient, body: dict[str, Any]) -> None:
    response = client.post(LOGIN_URL, json=body)

    assert response.status_code == 422


def test_login_upgrades_an_outdated_password_hash(
    client: TestClient, db: Session, user: User, user_password: str
) -> None:
    weak_hash = PasswordHasher(time_cost=1, memory_cost=8, parallelism=1).hash(user_password)
    user.password_hash = weak_hash
    db.commit()

    response = client.post(LOGIN_URL, json={"email": user.email, "password": user_password})

    assert response.status_code == 200
    db.expire_all()
    upgraded = db.get(User, user.id)
    assert upgraded is not None
    assert upgraded.password_hash != weak_hash
    assert not password_needs_rehash(upgraded.password_hash)
    assert verify_password(user_password, upgraded.password_hash)


def test_login_keeps_an_up_to_date_hash(
    client: TestClient, db: Session, user: User, user_password: str
) -> None:
    original_hash = user.password_hash

    client.post(LOGIN_URL, json={"email": user.email, "password": user_password})

    db.expire_all()
    current = db.get(User, user.id)
    assert current is not None
    assert current.password_hash == original_hash


# --------------------------------------------------------------------------------------------
# Rate limiting: 5 failures / 5 minutes per (email, client IP)
# --------------------------------------------------------------------------------------------


def _fail_login(client: TestClient, email: str, times: int) -> None:
    for _ in range(times):
        response = client.post(LOGIN_URL, json={"email": email, "password": "wrong-password"})
        assert response.status_code == 401


def test_login_is_rate_limited_after_five_failures(
    client: TestClient, user: User, user_password: str
) -> None:
    _fail_login(client, user.email, 5)

    # Blocked even with the right password, so guessing gains nothing during the window.
    response = client.post(LOGIN_URL, json={"email": user.email, "password": user_password})

    assert response.status_code == 429
    assert 0 < int(response.headers["retry-after"]) <= 300
    assert "access_token" not in response.text


def test_browsers_may_read_retry_after_on_a_rate_limited_login(
    client: TestClient, user: User
) -> None:
    origin = "http://localhost:8081"  # the CORS origin configured by the settings fixture
    _fail_login(client, user.email, 5)

    response = client.post(
        LOGIN_URL,
        json={"email": user.email, "password": "wrong-password"},
        headers={"Origin": origin},
    )

    assert response.status_code == 429
    assert response.headers["access-control-allow-origin"] == origin
    assert "retry-after" in response.headers["access-control-expose-headers"].lower()


def test_rate_limit_key_ignores_email_case(client: TestClient, user: User) -> None:
    _fail_login(client, user.email.upper(), 5)

    response = client.post(LOGIN_URL, json={"email": user.email, "password": "wrong-password"})

    assert response.status_code == 429


def test_rate_limit_applies_to_unknown_emails_too(client: TestClient) -> None:
    _fail_login(client, "nobody@example.com", 5)

    response = client.post(
        LOGIN_URL, json={"email": "nobody@example.com", "password": "wrong-password"}
    )

    assert response.status_code == 429


def test_rate_limit_is_per_email(client: TestClient, user: User, user_password: str) -> None:
    _fail_login(client, "someone-else@example.com", 5)

    response = client.post(LOGIN_URL, json={"email": user.email, "password": user_password})

    assert response.status_code == 200


def test_rate_limit_is_per_client_ip(client: TestClient, user: User, user_password: str) -> None:
    _fail_login(client, user.email, 5)

    with TestClient(client.app, client=("203.0.113.7", 50000)) as other_ip:
        response = other_ip.post(LOGIN_URL, json={"email": user.email, "password": user_password})

    assert response.status_code == 200


def test_successful_login_resets_the_failure_count(
    client: TestClient, user: User, user_password: str
) -> None:
    _fail_login(client, user.email, 4)
    assert (
        client.post(LOGIN_URL, json={"email": user.email, "password": user_password}).status_code
        == 200
    )

    _fail_login(client, user.email, 4)
    response = client.post(LOGIN_URL, json={"email": user.email, "password": user_password})

    assert response.status_code == 200


def test_rate_limit_lifts_when_the_window_slides(
    client: TestClient, clock: FakeClock, user: User, user_password: str
) -> None:
    _fail_login(client, user.email, 5)
    blocked = client.post(LOGIN_URL, json={"email": user.email, "password": user_password})
    assert blocked.status_code == 429
    assert blocked.headers["retry-after"] == "300"

    clock.now += 299
    still_blocked = client.post(LOGIN_URL, json={"email": user.email, "password": user_password})
    assert still_blocked.status_code == 429
    assert still_blocked.headers["retry-after"] == "1"

    clock.now += 1
    response = client.post(LOGIN_URL, json={"email": user.email, "password": user_password})

    assert response.status_code == 200
