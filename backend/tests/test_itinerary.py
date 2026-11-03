"""Visiting-order solvers and Google Maps directions URLs."""

import random
from itertools import permutations
from urllib.parse import parse_qs, urlsplit

import pytest

from app.schemas import TravelMode
from app.services import itinerary
from app.services.itinerary import (
    HELD_KARP_MAX_STORES,
    UnknownStoresError,
    google_maps_url,
    held_karp_order,
    improve_two_opt,
    nearest_neighbour_order,
    route_cost,
    solve_order,
)
from app.services.routing import Point

Matrix = list[list[float]]


def random_matrix(rng: random.Random, size: int, *, symmetric: bool = False) -> Matrix:
    """Random travel times in minutes; asymmetric unless asked otherwise (one-way streets)."""
    matrix = [[0.0] * size for _ in range(size)]
    for i in range(size):
        for j in range(size):
            if i == j:
                continue
            if symmetric and j < i:
                matrix[i][j] = matrix[j][i]
            else:
                matrix[i][j] = round(rng.uniform(1, 60), 3)
    return matrix


def line_matrix(positions: list[float]) -> Matrix:
    """Travel times between points on a straight road (node 0 is the start)."""
    return [[abs(a - b) for b in positions] for a in positions]


def brute_force_cost(durations: Matrix, *, return_to_start: bool) -> float:
    stores = range(1, len(durations))
    return min(
        route_cost(order, durations, return_to_start=return_to_start)
        for order in permutations(stores)
    )


def is_permutation_of_stores(order: list[int], size: int) -> bool:
    return sorted(order) == list(range(1, size))


# --------------------------------------------------------------------------------------------
# Costs and edge cases
# --------------------------------------------------------------------------------------------


def test_route_cost_adds_the_return_leg_only_when_asked() -> None:
    durations = [[0, 1, 9], [2, 0, 3], [7, 4, 0]]

    assert route_cost([1, 2], durations, return_to_start=False) == 1 + 3
    assert route_cost([1, 2], durations, return_to_start=True) == 1 + 3 + 7
    assert route_cost([], durations, return_to_start=True) == 0


def test_single_store_is_the_only_stop() -> None:
    assert solve_order([[0, 5], [6, 0]], return_to_start=False) == [1]
    assert solve_order([[0, 5], [6, 0]], return_to_start=True) == [1]


def test_start_alone_has_no_stops() -> None:
    assert solve_order([[0.0]], return_to_start=True) == []
    assert held_karp_order([[0.0]], return_to_start=False) == []
    assert nearest_neighbour_order([[0.0]]) == []


@pytest.mark.parametrize("durations", [[], [[0, 1], [1]], [[0, 1, 2], [1, 0, 2]]])
def test_non_square_matrices_are_rejected(durations: Matrix) -> None:
    with pytest.raises(ValueError, match="square"):
        solve_order(durations, return_to_start=False)


# --------------------------------------------------------------------------------------------
# Held-Karp
# --------------------------------------------------------------------------------------------


@pytest.mark.parametrize("return_to_start", [False, True])
@pytest.mark.parametrize("symmetric", [False, True])
def test_held_karp_matches_the_brute_force_optimum(return_to_start: bool, symmetric: bool) -> None:
    rng = random.Random(20261102)  # noqa: S311 (deterministic test data, not security)
    for _ in range(40):
        size = rng.randint(2, 8)  # 1 to 7 stores
        durations = random_matrix(rng, size, symmetric=symmetric)

        order = held_karp_order(durations, return_to_start=return_to_start)

        assert is_permutation_of_stores(order, size)
        assert route_cost(order, durations, return_to_start=return_to_start) == pytest.approx(
            brute_force_cost(durations, return_to_start=return_to_start)
        )


def test_solve_order_is_exact_up_to_twelve_stores() -> None:
    # Stores scattered along one road, start at one end: the only optimum is to drive along it.
    rng = random.Random(7)  # noqa: S311 (deterministic test data, not security)
    positions = rng.sample(range(1, 500), HELD_KARP_MAX_STORES)
    durations = line_matrix([0, *positions])

    order = solve_order(durations, return_to_start=False)

    assert [positions[node - 1] for node in order] == sorted(positions)


def test_return_to_start_changes_the_best_order() -> None:
    # Store 2 -> start is very slow (one-way street), so a round trip must end at store 1.
    durations = [
        [0, 1, 5],
        [1, 0, 1],
        [100, 5, 0],
    ]

    assert solve_order(durations, return_to_start=False) == [1, 2]
    assert solve_order(durations, return_to_start=True) == [2, 1]


def test_held_karp_is_deterministic_on_ties() -> None:
    durations = line_matrix([0, 1, 1, 1])

    first = held_karp_order(durations, return_to_start=True)

    assert all(held_karp_order(durations, return_to_start=True) == first for _ in range(3))


# --------------------------------------------------------------------------------------------
# Nearest neighbour + 2-opt
# --------------------------------------------------------------------------------------------


def test_nearest_neighbour_always_takes_the_closest_store() -> None:
    durations = line_matrix([0, 4, 1, 10, 2])

    assert nearest_neighbour_order(durations) == [2, 4, 1, 3]


@pytest.mark.parametrize("return_to_start", [False, True])
def test_two_opt_is_never_worse_than_nearest_neighbour(return_to_start: bool) -> None:
    rng = random.Random(42)  # noqa: S311 (deterministic test data, not security)
    strictly_better = 0
    for _ in range(30):
        size = rng.randint(HELD_KARP_MAX_STORES + 2, 20)
        durations = random_matrix(rng, size, symmetric=rng.random() < 0.5)
        greedy = nearest_neighbour_order(durations)

        improved = improve_two_opt(greedy, durations, return_to_start=return_to_start)

        assert is_permutation_of_stores(greedy, size)
        assert is_permutation_of_stores(improved, size)
        greedy_cost = route_cost(greedy, durations, return_to_start=return_to_start)
        improved_cost = route_cost(improved, durations, return_to_start=return_to_start)
        assert improved_cost <= greedy_cost
        strictly_better += improved_cost < greedy_cost
    # 2-opt must actually do something on random instances.
    assert strictly_better > 0


def test_two_opt_result_is_a_local_optimum() -> None:
    rng = random.Random(3)  # noqa: S311 (deterministic test data, not security)
    durations = random_matrix(rng, 15)

    order = improve_two_opt(nearest_neighbour_order(durations), durations, return_to_start=False)

    cost = route_cost(order, durations, return_to_start=False)
    for i in range(len(order) - 1):
        for j in range(i + 1, len(order)):
            neighbour = order[:i] + order[i : j + 1][::-1] + order[j + 1 :]
            assert route_cost(neighbour, durations, return_to_start=False) >= cost - 1e-9


def test_two_opt_untangles_a_crossing() -> None:
    # Square corners visited diagonally (a crossing) versus around the edge.
    corners: list[Point] = [(0, 0), (0, 1), (1, 1), (1, 0)]
    durations = [
        [((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5 for b in corners] for a in corners
    ]

    assert improve_two_opt([2, 1, 3], durations, return_to_start=True) in ([1, 2, 3], [3, 2, 1])


def test_more_than_twelve_stores_use_nearest_neighbour_and_two_opt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def exact_solver_is_too_slow(*_args: object, **_kwargs: object) -> list[int]:
        raise AssertionError("Held-Karp must not run above the threshold")

    monkeypatch.setattr(itinerary, "held_karp_order", exact_solver_is_too_slow)
    rng = random.Random(11)  # noqa: S311 (deterministic test data, not security)
    durations = random_matrix(rng, HELD_KARP_MAX_STORES + 2)

    order = solve_order(durations, return_to_start=True)

    expected = improve_two_opt(nearest_neighbour_order(durations), durations, return_to_start=True)
    assert order == expected


# --------------------------------------------------------------------------------------------
# Google Maps URL
# --------------------------------------------------------------------------------------------

START: Point = (45.5017, -73.5673)
FIRST: Point = (45.5088, -73.554)
SECOND: Point = (45.495, -73.58)
THIRD: Point = (45.52, -73.6)


def query_of(url: str) -> dict[str, str]:
    parts = urlsplit(url)
    assert f"{parts.scheme}://{parts.netloc}{parts.path}" == "https://www.google.com/maps/dir/"
    return {key: values[0] for key, values in parse_qs(parts.query, strict_parsing=True).items()}


def test_maps_url_ends_at_the_last_stop() -> None:
    url = google_maps_url(START, [FIRST, SECOND, THIRD], "driving", return_to_start=False)

    assert url.startswith("https://www.google.com/maps/dir/?api=1&origin=")
    assert query_of(url) == {
        "api": "1",
        "origin": "45.501700,-73.567300",
        "destination": "45.520000,-73.600000",
        "waypoints": "45.508800,-73.554000|45.495000,-73.580000",
        "travelmode": "driving",
    }


def test_maps_url_is_percent_encoded() -> None:
    url = google_maps_url(START, [FIRST, SECOND, THIRD], "driving", return_to_start=False)

    assert "waypoints=45.508800%2C-73.554000%7C45.495000%2C-73.580000" in url
    assert "|" not in url
    assert "," not in url


def test_maps_url_round_trip_returns_to_the_start() -> None:
    query = query_of(google_maps_url(START, [FIRST, SECOND], "walking", return_to_start=True))

    assert query["destination"] == query["origin"] == "45.501700,-73.567300"
    assert query["waypoints"] == "45.508800,-73.554000|45.495000,-73.580000"


def test_maps_url_single_store_has_no_waypoints() -> None:
    query = query_of(google_maps_url(START, [FIRST], "driving", return_to_start=False))

    assert query["destination"] == "45.508800,-73.554000"
    assert "waypoints" not in query


def test_maps_url_without_stores_goes_nowhere() -> None:
    query = query_of(google_maps_url(START, [], "driving", return_to_start=False))

    assert query["destination"] == query["origin"]
    assert "waypoints" not in query


@pytest.mark.parametrize(
    ("mode", "google_mode"),
    [("driving", "driving"), ("walking", "walking"), ("cycling", "bicycling")],
)
def test_maps_url_travel_modes(mode: TravelMode, google_mode: str) -> None:
    url = google_maps_url(START, [FIRST], mode, return_to_start=False)

    assert query_of(url)["travelmode"] == google_mode


def test_unknown_stores_error_lists_every_missing_id() -> None:
    error = UnknownStoresError([12, 7])

    assert error.store_ids == [12, 7]
    assert str(error) == "Unknown store ids: 12, 7"
