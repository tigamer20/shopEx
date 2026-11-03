"""Authentication and admin-token dependencies."""

from collections.abc import Iterator
from datetime import timedelta

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.config import Settings, get_settings
from app.db import get_db
from app.deps import CurrentUser, require_admin_token
from app.models import User
from app.security import create_access_token


@pytest.fixture
def guarded_client(session_factory: sessionmaker[Session]) -> Iterator[TestClient]:
    """Minimal app exposing one user-protected and one admin-protected route."""
    app = FastAPI()

    @app.get("/me")
    def me(user: CurrentUser) -> dict[str, int]:
        return {"id": user.id}

    @app.post("/admin", dependencies=[Depends(require_admin_token)])
    def admin() -> dict[str, bool]:
        return {"ok": True}

    def override_get_db() -> Iterator[Session]:
        with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client


def test_valid_token_resolves_the_user(
    guarded_client: TestClient, user: User, auth_headers: dict[str, str]
) -> None:
    response = guarded_client.get("/me", headers=auth_headers)

    assert response.status_code == 200
    assert response.json() == {"id": user.id}


@pytest.mark.parametrize(
    "headers",
    [
        {},
        {"Authorization": "Bearer not-a-jwt"},
        {"Authorization": "Basic dXNlcjpwYXNz"},
    ],
)
def test_missing_or_invalid_credentials_get_401(
    guarded_client: TestClient, headers: dict[str, str]
) -> None:
    response = guarded_client.get("/me", headers=headers)

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_expired_token_gets_401(guarded_client: TestClient, user: User, settings: Settings) -> None:
    token = create_access_token(user.id, settings=settings, expires_delta=timedelta(seconds=-5))

    response = guarded_client.get("/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 401


def test_token_of_deleted_user_gets_401(
    guarded_client: TestClient, db: Session, user: User, auth_headers: dict[str, str]
) -> None:
    db.delete(user)
    db.commit()

    response = guarded_client.get("/me", headers=auth_headers)

    assert response.status_code == 401


def test_admin_route_accepts_the_right_token(
    guarded_client: TestClient, admin_headers: dict[str, str]
) -> None:
    response = guarded_client.post("/admin", headers=admin_headers)

    assert response.status_code == 200


@pytest.mark.parametrize("headers", [{}, {"X-Admin-Token": "wrong-token"}])
def test_admin_route_rejects_a_wrong_or_missing_token(
    guarded_client: TestClient, headers: dict[str, str]
) -> None:
    response = guarded_client.post("/admin", headers=headers)

    assert response.status_code == 403


def test_admin_route_is_hidden_when_no_token_is_configured(
    guarded_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ADMIN_TOKEN", "")
    get_settings.cache_clear()

    response = guarded_client.post("/admin", headers={"X-Admin-Token": ""})

    assert response.status_code == 404
