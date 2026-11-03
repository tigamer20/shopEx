"""``GET /health`` and ``POST /admin/refresh`` (X-Admin-Token guard, refresh summary)."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import __version__
from app.config import get_settings
from app.db import utcnow
from app.models import AreaFetch

from .conftest import OutboundHttp
from .factories import HOME, install_overpass, three_shops

URL = "/api/v1/admin/refresh"


def test_health_is_public(client: TestClient) -> None:
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": __version__}


def test_refresh_does_not_exist_without_admin_token(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("ADMIN_TOKEN")
    get_settings.cache_clear()

    response = client.post(URL, headers={"X-Admin-Token": "anything"})

    assert response.status_code == 404


@pytest.mark.parametrize("headers", [{}, {"X-Admin-Token": "wrong"}, {"X-Admin-Token": ""}])
def test_refresh_rejects_a_missing_or_wrong_token(
    client: TestClient, headers: dict[str, str]
) -> None:
    assert client.post(URL, headers=headers).status_code == 403


def test_refresh_ignores_user_bearer_tokens(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    assert client.post(URL, headers=auth_headers).status_code == 403


def test_refresh_with_nothing_known_is_a_no_op(
    client: TestClient, admin_headers: dict[str, str], outbound_http: OutboundHttp
) -> None:
    response = client.post(URL, headers=admin_headers)

    assert response.status_code == 200
    payload = response.json()
    assert (payload["areas_refreshed"], payload["stores_refreshed"], payload["prices_updated"]) == (
        0,
        0,
        0,
    )
    assert datetime.fromisoformat(payload["started_at"]) <= datetime.fromisoformat(
        payload["finished_at"]
    )
    assert outbound_http.requests == []


def test_refresh_rediscovers_stale_areas(
    client: TestClient,
    admin_headers: dict[str, str],
    auth_headers: dict[str, str],
    outbound_http: OutboundHttp,
    db: Session,
) -> None:
    install_overpass(outbound_http, three_shops())
    stores = client.get(
        "/api/v1/stores",
        params={"lat": HOME[0], "lon": HOME[1], "radius_km": 5},
        headers=auth_headers,
    )
    assert stores.status_code == 200
    area = db.scalar(select(AreaFetch))
    assert area is not None
    area.fetched_at = utcnow() - timedelta(days=2)
    db.commit()

    response = client.post(URL, headers=admin_headers)

    assert response.status_code == 200
    payload = response.json()
    assert payload["areas_refreshed"] == 1
    # The stores were priced earlier today: their prices are kept.
    assert (payload["stores_refreshed"], payload["prices_updated"]) == (0, 0)
    assert len(outbound_http.requests) == 2
