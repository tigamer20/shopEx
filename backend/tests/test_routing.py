"""OSRM table/route parsing, profile mapping and the straight-line estimate fallback.

Every OSRM answer comes from an ``httpx.MockTransport``; no request leaves the process.
"""

from collections.abc import Callable
from typing import Any

import httpx
import pytest

from app.config import Settings
from app.schemas import TravelMode
from app.services.geo import haversine_km
from app.services.routing import (
    DETOUR_FACTOR,
    ESTIMATE_SPEED_KMH,
    USER_AGENT,
    Point,
    estimate_matrix,
    route_geometry,
    travel_matrix,
)

from .conftest import OutboundHttp

START: Point = (45.5017, -73.5673)
STORE_A: Point = (45.5088, -73.5540)
STORE_B: Point = (45.4950, -73.5800)
POINTS = [START, STORE_A, STORE_B]
COORDINATES = "-73.567300,45.501700;-73.554000,45.508800;-73.580000,45.495000"

# OSRM units: seconds and metres.
DURATIONS_S = [[0, 120, 300], [130, 0, 240], [310, 250, 0]]
DISTANCES_M = [[0, 1500, 3000], [1600, 0, 2500], [3100, 2600, 0]]

Handler = Callable[[httpx.Request], httpx.Response]


def mock_client(handler: Handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def json_handler(payload: Any, status_code: int = 200) -> Handler:
    def handle(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code, json=payload)

    return handle


def table_payload(**overrides: Any) -> dict[str, Any]:
    return {"code": "Ok", "durations": DURATIONS_S, "distances": DISTANCES_M, **overrides}


# --------------------------------------------------------------------------------------------
# Estimate
# --------------------------------------------------------------------------------------------


@pytest.mark.parametrize("mode", ["driving", "walking", "cycling"])
def test_estimate_is_haversine_with_detour_at_mode_speed(mode: TravelMode) -> None:
    matrix = estimate_matrix(POINTS, mode)

    assert matrix.source == "estimate"
    expected_km = DETOUR_FACTOR * haversine_km(*START, *STORE_A)
    assert matrix.distances_km[0][1] == pytest.approx(expected_km)
    assert matrix.durations_min[0][1] == pytest.approx(expected_km / ESTIMATE_SPEED_KMH[mode] * 60)
    assert [matrix.durations_min[i][i] for i in range(3)] == [0, 0, 0]
    assert matrix.distances_km[1][2] == pytest.approx(matrix.distances_km[2][1])


def test_estimate_speeds_match_the_contract() -> None:
    assert ESTIMATE_SPEED_KMH == {"driving": 35.0, "cycling": 15.0, "walking": 5.0}
    assert DETOUR_FACTOR == 1.3


# --------------------------------------------------------------------------------------------
# OSRM table
# --------------------------------------------------------------------------------------------


def test_table_is_parsed_into_minutes_and_kilometres(settings: Settings) -> None:
    requests: list[httpx.Request] = []

    def handle(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json=table_payload())

    with mock_client(handle) as client:
        matrix = travel_matrix(POINTS, "driving", settings=settings, client=client)

    assert matrix.source == "osrm"
    assert matrix.durations_min == [[0, 2, 5], [130 / 60, 0, 4], [310 / 60, 250 / 60, 0]]
    assert matrix.distances_km == [[0, 1.5, 3], [1.6, 0, 2.5], [3.1, 2.6, 0]]

    (request,) = requests
    assert request.method == "GET"
    assert request.url.host == "osrm.invalid"
    assert request.url.raw_path.decode() == (
        f"/table/v1/car/{COORDINATES}?annotations=duration,distance"
    )
    assert request.headers["User-Agent"] == USER_AGENT
    assert request.extensions["timeout"]["read"] == settings.http_timeout_s


@pytest.mark.parametrize(
    ("mode", "profile"), [("driving", "car"), ("walking", "foot"), ("cycling", "bike")]
)
def test_travel_modes_map_to_osrm_profiles(
    settings: Settings, mode: TravelMode, profile: str
) -> None:
    paths: list[str] = []

    def handle(request: httpx.Request) -> httpx.Response:
        paths.append(request.url.path)
        return httpx.Response(200, json=table_payload())

    with mock_client(handle) as client:
        travel_matrix(POINTS, mode, settings=settings, client=client)

    assert paths == [f"/table/v1/{profile}/{COORDINATES}"]


def test_trailing_slash_in_osrm_url_is_ignored(settings: Settings) -> None:
    paths: list[str] = []

    def handle(request: httpx.Request) -> httpx.Response:
        paths.append(request.url.path)
        return httpx.Response(200, json=table_payload())

    custom = settings.model_copy(update={"osrm_url": "http://osrm.invalid/osrm/"})
    with mock_client(handle) as client:
        travel_matrix(POINTS, "driving", settings=custom, client=client)

    assert paths == [f"/osrm/table/v1/car/{COORDINATES}"]


def test_unroutable_pairs_are_filled_from_the_estimate(settings: Settings) -> None:
    durations = [[0, None, 300], [130, 0, 240], [310, 250, 0]]
    distances = [[0, None, 3000], [1600, 0, 2500], [3100, 2600, 0]]
    estimate = estimate_matrix(POINTS, "driving")

    payload = table_payload(durations=durations, distances=distances)
    with mock_client(json_handler(payload)) as client:
        matrix = travel_matrix(POINTS, "driving", settings=settings, client=client)

    assert matrix.source == "osrm"
    assert matrix.durations_min[0][1] == pytest.approx(estimate.durations_min[0][1])
    assert matrix.distances_km[0][1] == pytest.approx(estimate.distances_km[0][1])
    assert matrix.durations_min[0][2] == 5


def test_missing_distance_matrix_uses_estimated_distances(settings: Settings) -> None:
    payload = {"code": "Ok", "durations": DURATIONS_S}
    with mock_client(json_handler(payload)) as client:
        matrix = travel_matrix(POINTS, "cycling", settings=settings, client=client)

    assert matrix.source == "osrm"
    assert matrix.durations_min[0][1] == 2
    assert matrix.distances_km == estimate_matrix(POINTS, "cycling").distances_km


def _raise(error: type[httpx.TransportError]) -> Handler:
    def handle(request: httpx.Request) -> httpx.Response:
        raise error("simulated", request=request)

    return handle


def _not_json(_request: httpx.Request) -> httpx.Response:
    return httpx.Response(200, text="<html>Bad gateway</html>")


@pytest.mark.parametrize(
    "handler",
    [
        pytest.param(_raise(httpx.ReadTimeout), id="read-timeout"),
        pytest.param(_raise(httpx.ConnectTimeout), id="connect-timeout"),
        pytest.param(_raise(httpx.ConnectError), id="unreachable"),
        pytest.param(json_handler({"code": "Ok"}, status_code=500), id="http-500"),
        pytest.param(json_handler({"code": "InvalidQuery"}, status_code=400), id="http-400"),
        pytest.param(json_handler({}, status_code=301), id="redirect"),
        pytest.param(_not_json, id="not-json"),
        pytest.param(json_handler([1, 2, 3]), id="not-an-object"),
        pytest.param(json_handler(table_payload(code="NoTable")), id="error-code"),
        pytest.param(json_handler({"code": "Ok"}), id="no-durations"),
        pytest.param(json_handler(table_payload(durations=[[0, 1], [1, 0]])), id="too-few-rows"),
        pytest.param(
            json_handler(table_payload(durations=[[0, 1], [1, 0], [2, 2]])), id="short-rows"
        ),
        pytest.param(json_handler(table_payload(durations=[0, 1, 2])), id="flat-list"),
        pytest.param(
            json_handler(table_payload(durations=[[0, -1, 2], [1, 0, 2], [2, 2, 0]])),
            id="negative",
        ),
        pytest.param(
            json_handler(table_payload(durations=[[0, "1", 2], [1, 0, 2], [2, 2, 0]])),
            id="string",
        ),
        pytest.param(
            json_handler(table_payload(durations=[[0, True, 2], [1, 0, 2], [2, 2, 0]])),
            id="boolean",
        ),
        pytest.param(json_handler(table_payload(distances=[[0, 1], [1, 0]])), id="bad-distances"),
    ],
)
def test_any_osrm_failure_falls_back_to_the_estimate(settings: Settings, handler: Handler) -> None:
    with mock_client(handler) as client:
        matrix = travel_matrix(POINTS, "walking", settings=settings, client=client)

    assert matrix == estimate_matrix(POINTS, "walking")


def test_timeout_fallback_keeps_the_matrix_shape(settings: Settings) -> None:
    with mock_client(_raise(httpx.ReadTimeout)) as client:
        matrix = travel_matrix(POINTS, "driving", settings=settings, client=client)

    assert matrix.source == "estimate"
    assert len(matrix.durations_min) == len(matrix.distances_km) == len(POINTS)
    assert all(len(row) == len(POINTS) for row in matrix.durations_min + matrix.distances_km)


def test_a_single_point_needs_no_request(settings: Settings) -> None:
    def fail(_request: httpx.Request) -> httpx.Response:
        raise AssertionError("OSRM must not be called")

    with mock_client(fail) as client:
        matrix = travel_matrix([START], "driving", settings=settings, client=client)

    assert matrix.durations_min == [[0.0]]
    assert matrix.source == "estimate"


def test_non_finite_coordinates_are_rejected(settings: Settings) -> None:
    with pytest.raises(ValueError, match="finite"):
        travel_matrix([START, (float("nan"), 0.0)], "driving", settings=settings)


def test_default_client_is_used_when_none_is_given(
    settings: Settings, outbound_http: OutboundHttp
) -> None:
    # Outbound HTTP is blocked by default: the built-in client falls back to the estimate...
    assert travel_matrix(POINTS, "driving", settings=settings).source == "estimate"

    # ...and reaches "OSRM" once a fake server answers.
    outbound_http.install(json_handler(table_payload()))
    assert travel_matrix(POINTS, "driving", settings=settings).source == "osrm"


# --------------------------------------------------------------------------------------------
# OSRM route geometry
# --------------------------------------------------------------------------------------------


def route_payload(coordinates: Any) -> dict[str, Any]:
    return {
        "code": "Ok",
        "routes": [{"geometry": {"type": "LineString", "coordinates": coordinates}}],
        "waypoints": [],
    }


def test_route_geometry_is_converted_to_lat_lon(settings: Settings) -> None:
    requests: list[httpx.Request] = []
    lon_lat = [[-73.5673, 45.5017], [-73.56, 45.505], [-73.554, 45.5088]]

    def handle(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json=route_payload(lon_lat))

    with mock_client(handle) as client:
        geometry = route_geometry([START, STORE_A], "walking", settings=settings, client=client)

    assert geometry == [(45.5017, -73.5673), (45.505, -73.56), (45.5088, -73.554)]
    (request,) = requests
    assert request.url.raw_path.decode() == (
        "/route/v1/foot/-73.567300,45.501700;-73.554000,45.508800?overview=full&geometries=geojson"
    )
    assert request.extensions["timeout"]["read"] == settings.http_timeout_s


@pytest.mark.parametrize(
    "handler",
    [
        pytest.param(_raise(httpx.ReadTimeout), id="timeout"),
        pytest.param(json_handler({"code": "NoRoute"}, status_code=400), id="http-400"),
        pytest.param(json_handler({"code": "NoRoute", "routes": []}), id="error-code"),
        pytest.param(json_handler({"code": "Ok", "routes": []}), id="no-routes"),
        pytest.param(json_handler({"code": "Ok", "routes": ["x"]}), id="route-not-object"),
        pytest.param(json_handler({"code": "Ok", "routes": [{}]}), id="no-geometry"),
        pytest.param(json_handler(route_payload("polyline")), id="encoded-polyline"),
        pytest.param(json_handler(route_payload([[-73.5, 45.5]])), id="single-position"),
        pytest.param(json_handler(route_payload([[-73.5, 45.5], [1]])), id="short-position"),
        pytest.param(json_handler(route_payload([[-73.5, 45.5], ["a", "b"]])), id="strings"),
        pytest.param(json_handler(route_payload([[-73.5, 45.5], [0, 95]])), id="lat-range"),
        pytest.param(json_handler(route_payload([[-73.5, 45.5], [190, 45]])), id="lon-range"),
        pytest.param(_not_json, id="not-json"),
    ],
)
def test_route_geometry_failures_return_none(settings: Settings, handler: Handler) -> None:
    with mock_client(handler) as client:
        assert route_geometry(POINTS, "driving", settings=settings, client=client) is None


def test_route_geometry_needs_two_points(settings: Settings) -> None:
    def fail(_request: httpx.Request) -> httpx.Response:
        raise AssertionError("OSRM must not be called")

    with mock_client(fail) as client:
        assert route_geometry([START], "driving", settings=settings, client=client) is None


def test_route_geometry_without_network_is_none(settings: Settings) -> None:
    assert route_geometry(POINTS, "driving", settings=settings) is None
