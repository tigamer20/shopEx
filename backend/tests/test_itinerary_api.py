"""``POST /api/v1/itinerary`` with routing mocked at the HTTP level (no network)."""

from typing import Any
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import Store, User
from app.services.geo import haversine_km

from .conftest import OutboundHttp

URL = "/api/v1/itinerary"

# Everything sits on one meridian, so straight-line distances add up exactly.
START = {"lat": 45.50, "lon": -73.57}


def add_store(db: Session, name: str, lat: float, lon: float = -73.57) -> Store:
    store = Store(
        name=name, chain=name, address=None, lat=lat, lon=lon, source="demo", price_tier="standard"
    )
    db.add(store)
    db.commit()
    db.refresh(store)
    return store


@pytest.fixture
def stores(db: Session) -> dict[str, Store]:
    """Three fictional stores north of the start, nearest first: near, middle, far."""
    return {
        "near": add_store(db, "Marché Lumière", 45.51),
        "middle": add_store(db, "Épicerie Boréale", 45.53),
        "far": add_store(db, "Fraîcheur Express", 45.56),
    }


def maps_query(body: dict[str, Any]) -> dict[str, str]:
    query = urlsplit(body["maps_url"]).query
    return {key: values[0] for key, values in parse_qs(query).items()}


def osrm_handler(durations_s: list[list[float]], distances_m: list[list[float]]) -> Any:
    """Fake OSRM: fixed table; the route geometry is simply the requested waypoints."""

    def handle(request: httpx.Request) -> httpx.Response:
        service, _version, _profile, coordinates = request.url.path.strip("/").split("/")
        if service == "table":
            return httpx.Response(
                200, json={"code": "Ok", "durations": durations_s, "distances": distances_m}
            )
        lon_lat = [[float(value) for value in pair.split(",")] for pair in coordinates.split(";")]
        return httpx.Response(
            200, json={"code": "Ok", "routes": [{"geometry": {"coordinates": lon_lat}}]}
        )

    return handle


def line_osrm_handler(positions_km: list[float]) -> Any:
    """Fake OSRM where points sit on a road at ``positions_km``, driven at 60 km/h."""
    distances = [[abs(a - b) * 1000 for b in positions_km] for a in positions_km]
    durations = [[abs(a - b) * 60 for b in positions_km] for a in positions_km]
    return osrm_handler(durations, distances)


def test_requires_authentication(client: TestClient, stores: dict[str, Store]) -> None:
    response = client.post(URL, json={"start": START, "store_ids": [stores["near"].id]})

    assert response.status_code == 401


def test_estimate_when_osrm_is_unreachable(
    client: TestClient,
    auth_headers: dict[str, str],
    stores: dict[str, Store],
    outbound_http: OutboundHttp,
) -> None:
    ids = [stores["far"].id, stores["near"].id, stores["middle"].id]

    response = client.post(URL, json={"start": START, "store_ids": ids}, headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["routing_source"] == "estimate"
    assert body["geometry"] is None
    assert [stop["store"]["name"] for stop in body["stops"]] == [
        "Marché Lumière",
        "Épicerie Boréale",
        "Fraîcheur Express",
    ]
    assert [stop["order"] for stop in body["stops"]] == [1, 2, 3]

    # The default travel mode is driving: 35 km/h on haversine x 1.3.
    first = body["stops"][0]
    assert first["store"]["distance_km"] == pytest.approx(1.11, abs=0.01)
    assert first["leg_distance_km"] == pytest.approx(1.3 * 1.112, abs=0.01)
    assert first["leg_duration_min"] == pytest.approx(first["leg_distance_km"] / 35 * 60, abs=0.01)

    legs = [stop["leg_duration_min"] for stop in body["stops"]]
    arrivals = [stop["arrival_min"] for stop in body["stops"]]
    assert arrivals == pytest.approx([sum(legs[: i + 1]) for i in range(3)], abs=0.02)
    assert body["total_duration_min"] == pytest.approx(arrivals[-1], abs=0.01)
    assert body["total_distance_km"] == pytest.approx(
        sum(stop["leg_distance_km"] for stop in body["stops"]), abs=0.02
    )
    # The table failed, so the route is not even tried (it would only wait for another timeout).
    assert [request.url.path.split("/")[1] for request in outbound_http.requests] == ["table"]


def test_osrm_matrix_drives_the_order_and_geometry(
    client: TestClient,
    auth_headers: dict[str, str],
    stores: dict[str, Store],
    outbound_http: OutboundHttp,
) -> None:
    # On the road, "far" is actually the first stop, then "near", then "middle".
    outbound_http.install(line_osrm_handler([0, 2, 3, 1]))
    ids = [stores["near"].id, stores["middle"].id, stores["far"].id]

    response = client.post(URL, json={"start": START, "store_ids": ids}, headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["routing_source"] == "osrm"
    assert [stop["store"]["id"] for stop in body["stops"]] == [
        stores["far"].id,
        stores["near"].id,
        stores["middle"].id,
    ]
    assert [stop["leg_duration_min"] for stop in body["stops"]] == [1, 1, 1]
    assert [stop["leg_distance_km"] for stop in body["stops"]] == [1, 1, 1]
    assert [stop["arrival_min"] for stop in body["stops"]] == [1, 2, 3]
    assert body["total_duration_min"] == 3
    assert body["total_distance_km"] == 3
    assert body["geometry"] == [[45.50, -73.57], [45.56, -73.57], [45.51, -73.57], [45.53, -73.57]]

    query = maps_query(body)
    assert query["origin"] == "45.500000,-73.570000"
    assert query["waypoints"] == "45.560000,-73.570000|45.510000,-73.570000"
    assert query["destination"] == "45.530000,-73.570000"

    table, route = outbound_http.requests
    assert table.url.path.startswith("/table/v1/car/")
    assert route.url.path.startswith("/route/v1/car/")


@pytest.mark.parametrize(
    ("return_to_start", "expected_order", "arrivals", "total_min", "total_km"),
    [(False, ["middle", "near"], [1, 2], 2, 2), (True, ["near", "middle"], [2, 3], 4, 4)],
)
def test_return_to_start_adds_the_way_back(
    client: TestClient,
    auth_headers: dict[str, str],
    stores: dict[str, Store],
    outbound_http: OutboundHttp,
    return_to_start: bool,
    expected_order: list[str],
    arrivals: list[float],
    total_min: float,
    total_km: float,
) -> None:
    # Nodes: start, middle, near. Coming back from "near" is slow (one-way streets), so a
    # round trip visits it first while a one-way trip ends there.
    durations_s = [[0, 60, 120], [60, 0, 60], [600, 60, 0]]
    distances_m = [[0, 1000, 2000], [1000, 0, 1000], [2000, 1000, 0]]
    outbound_http.install(osrm_handler(durations_s, distances_m))
    payload = {
        "start": START,
        "store_ids": [stores["middle"].id, stores["near"].id],
        "return_to_start": return_to_start,
    }

    body = client.post(URL, json=payload, headers=auth_headers).json()

    assert [stop["store"]["id"] for stop in body["stops"]] == [
        stores[name].id for name in expected_order
    ]
    assert [stop["arrival_min"] for stop in body["stops"]] == arrivals
    assert body["total_duration_min"] == total_min
    assert body["total_distance_km"] == total_km
    query = maps_query(body)
    if return_to_start:
        assert body["geometry"][0] == body["geometry"][-1] == [45.50, -73.57]
        assert query["destination"] == query["origin"]
        assert len(query["waypoints"].split("|")) == 2
    else:
        assert body["geometry"][-1] == [45.51, -73.57]
        assert query["destination"] == "45.510000,-73.570000"
        assert len(query["waypoints"].split("|")) == 1


def test_single_store(
    client: TestClient, auth_headers: dict[str, str], stores: dict[str, Store]
) -> None:
    response = client.post(
        URL, json={"start": START, "store_ids": [stores["middle"].id]}, headers=auth_headers
    )

    body = response.json()
    assert response.status_code == 200
    assert len(body["stops"]) == 1
    assert body["stops"][0]["order"] == 1
    assert body["stops"][0]["arrival_min"] == body["total_duration_min"]
    assert "waypoints" not in maps_query(body)


def test_user_travel_mode_is_the_default(
    client: TestClient,
    db: Session,
    user: User,
    auth_headers: dict[str, str],
    stores: dict[str, Store],
    outbound_http: OutboundHttp,
) -> None:
    user.travel_mode = "walking"
    db.commit()
    outbound_http.install(line_osrm_handler([0, 1]))

    response = client.post(
        URL, json={"start": START, "store_ids": [stores["near"].id]}, headers=auth_headers
    )

    assert maps_query(response.json())["travelmode"] == "walking"
    assert all("/v1/foot/" in request.url.path for request in outbound_http.requests)


def test_explicit_travel_mode_wins_over_the_user_preference(
    client: TestClient,
    db: Session,
    user: User,
    auth_headers: dict[str, str],
    stores: dict[str, Store],
    outbound_http: OutboundHttp,
) -> None:
    user.travel_mode = "walking"
    db.commit()
    outbound_http.install(line_osrm_handler([0, 1]))

    response = client.post(
        URL,
        json={"start": START, "store_ids": [stores["near"].id], "travel_mode": "cycling"},
        headers=auth_headers,
    )

    assert maps_query(response.json())["travelmode"] == "bicycling"
    assert all("/v1/bike/" in request.url.path for request in outbound_http.requests)


def test_estimate_speed_follows_the_travel_mode(
    client: TestClient, auth_headers: dict[str, str], stores: dict[str, Store]
) -> None:
    payload = {"start": START, "store_ids": [stores["near"].id], "travel_mode": "walking"}

    stop = client.post(URL, json=payload, headers=auth_headers).json()["stops"][0]

    road_km = 1.3 * haversine_km(START["lat"], START["lon"], 45.51, -73.57)
    assert stop["leg_distance_km"] == pytest.approx(road_km, abs=0.005)
    assert stop["leg_duration_min"] == pytest.approx(road_km / 5 * 60, abs=0.005)


def test_geometry_is_null_when_only_the_route_call_fails(
    client: TestClient,
    auth_headers: dict[str, str],
    stores: dict[str, Store],
    outbound_http: OutboundHttp,
) -> None:
    table_only = line_osrm_handler([0, 1])

    def handle(request: httpx.Request) -> httpx.Response:
        if "/route/" in request.url.path:
            raise httpx.ReadTimeout("simulated", request=request)
        return table_only(request)

    outbound_http.install(handle)

    response = client.post(
        URL, json={"start": START, "store_ids": [stores["near"].id]}, headers=auth_headers
    )

    body = response.json()
    assert body["routing_source"] == "osrm"
    assert body["geometry"] is None


def test_unknown_store_ids_are_listed_in_the_404(
    client: TestClient, auth_headers: dict[str, str], stores: dict[str, Store]
) -> None:
    ids = [stores["near"].id, 999_999, 888_888]

    response = client.post(URL, json={"start": START, "store_ids": ids}, headers=auth_headers)

    assert response.status_code == 404
    assert response.json() == {"detail": "Unknown store ids: 999999, 888888"}


@pytest.mark.parametrize(
    "payload",
    [
        pytest.param({"store_ids": [1]}, id="no-start"),
        pytest.param({"start": START, "store_ids": []}, id="no-stores"),
        pytest.param({"start": START, "store_ids": list(range(1, 17))}, id="too-many-stores"),
        pytest.param({"start": START, "store_ids": [1, 1]}, id="duplicates"),
        pytest.param({"start": START, "store_ids": [0]}, id="non-positive-id"),
        pytest.param({"start": {"lat": 91, "lon": 0}, "store_ids": [1]}, id="latitude"),
        pytest.param({"start": START, "store_ids": [1], "travel_mode": "flying"}, id="mode"),
        pytest.param({"start": START, "store_ids": [1], "avoid": "tolls"}, id="unknown-field"),
    ],
)
def test_invalid_requests_are_rejected(
    client: TestClient, auth_headers: dict[str, str], payload: dict[str, Any]
) -> None:
    response = client.post(URL, json=payload, headers=auth_headers)

    assert response.status_code == 422
