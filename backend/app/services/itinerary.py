"""Store visiting order and itinerary assembly (ARCHITECTURE.md section 4 "Itinerary").

Order minimises total duration: exact Held-Karp DP for up to 12 stores, otherwise nearest
neighbour + 2-opt. ``maps_url`` is a Google Maps directions URL
(``https://www.google.com/maps/dir/?api=1&origin=..&destination=..&waypoints=a|b&travelmode=..``).

Solvers work on a duration matrix whose node 0 is the start and nodes ``1..n-1`` are the stores.
Matrices may be asymmetric (one-way streets), so every cost is computed in travel direction.
"""

from __future__ import annotations

from collections.abc import Sequence
from itertools import pairwise
from urllib.parse import urlencode

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import schemas
from app.config import Settings
from app.models import Store, User
from app.schemas import TravelMode
from app.services.geo import haversine_km
from app.services.routing import Point, http_client, route_geometry, travel_matrix

HELD_KARP_MAX_STORES = 12

GOOGLE_MAPS_DIRECTIONS_URL = "https://www.google.com/maps/dir/"
GOOGLE_TRAVEL_MODES: dict[TravelMode, str] = {
    "driving": "driving",
    "walking": "walking",
    "cycling": "bicycling",
}

# 2-opt only accepts moves that save more than this, so float noise cannot make it loop.
_MIN_IMPROVEMENT = 1e-9

Matrix = Sequence[Sequence[float]]


class UnknownStoresError(LookupError):
    """Some requested store ids do not exist."""

    def __init__(self, store_ids: Sequence[int]) -> None:
        self.store_ids = list(store_ids)
        super().__init__(f"Unknown store ids: {', '.join(map(str, self.store_ids))}")


# --------------------------------------------------------------------------------------------
# Visiting order
# --------------------------------------------------------------------------------------------


def route_cost(order: Sequence[int], durations: Matrix, *, return_to_start: bool) -> float:
    """Total duration of leaving node 0, visiting ``order`` and optionally coming back."""
    path = [0, *order, 0] if return_to_start else [0, *order]
    return sum(durations[origin][destination] for origin, destination in pairwise(path))


def solve_order(durations: Matrix, *, return_to_start: bool) -> list[int]:
    """Visiting order of nodes ``1..n-1`` (node 0 is the start) minimising total duration."""
    size = len(durations)
    if size == 0 or any(len(row) != size for row in durations):
        raise ValueError("durations must be a non-empty square matrix")
    if size - 1 <= HELD_KARP_MAX_STORES:
        return held_karp_order(durations, return_to_start=return_to_start)
    order = nearest_neighbour_order(durations)
    return improve_two_opt(order, durations, return_to_start=return_to_start)


def held_karp_order(durations: Matrix, *, return_to_start: bool) -> list[int]:
    """Exact optimum by dynamic programming over subsets: O(2^n * n^2) time, O(2^n * n) memory.

    ``cost[mask][j]`` is the cheapest path that leaves the start, visits exactly the stores in
    ``mask`` (bit ``j`` = node ``j + 1``) and ends at node ``j + 1``.
    """
    stores = len(durations) - 1
    if stores <= 0:
        return []
    full_mask = (1 << stores) - 1
    infinity = float("inf")
    cost = [[infinity] * stores for _ in range(full_mask + 1)]
    parent = [[-1] * stores for _ in range(full_mask + 1)]
    for j in range(stores):
        cost[1 << j][j] = durations[0][j + 1]

    # Every subset is built from smaller ones, so increasing mask order is a valid DP order.
    for mask in range(1, full_mask + 1):
        for j in range(stores):
            if not mask & (1 << j) or cost[mask][j] == infinity:
                continue
            leaving = durations[j + 1]
            for k in range(stores):
                if mask & (1 << k):
                    continue
                candidate = cost[mask][j] + leaving[k + 1]
                next_mask = mask | (1 << k)
                if candidate < cost[next_mask][k]:
                    cost[next_mask][k] = candidate
                    parent[next_mask][k] = j

    def total(last: int) -> float:
        closing = durations[last + 1][0] if return_to_start else 0.0
        return cost[full_mask][last] + closing

    # min() keeps the first of equal candidates, so the answer is deterministic.
    last = min(range(stores), key=total)
    order: list[int] = []
    mask = full_mask
    while last != -1:
        order.append(last + 1)
        previous = parent[mask][last]
        mask &= ~(1 << last)
        last = previous
    order.reverse()
    return order


def nearest_neighbour_order(durations: Matrix) -> list[int]:
    """Greedy order: always go to the closest store not visited yet (ties: lowest node)."""
    remaining = list(range(1, len(durations)))
    order: list[int] = []
    current = 0
    while remaining:
        current = min(remaining, key=durations[current].__getitem__)
        remaining.remove(current)
        order.append(current)
    return order


def improve_two_opt(order: Sequence[int], durations: Matrix, *, return_to_start: bool) -> list[int]:
    """Reverse sub-sequences of ``order`` while that shortens the route; never makes it worse.

    The cost is recomputed for each candidate rather than patched, which keeps asymmetric
    matrices correct; with at most 15 stores per request that stays well under a millisecond
    per pass.
    """
    best = list(order)
    best_cost = route_cost(best, durations, return_to_start=return_to_start)
    improved = True
    while improved:
        improved = False
        for i in range(len(best) - 1):
            for j in range(i + 1, len(best)):
                candidate = best[:i] + best[i : j + 1][::-1] + best[j + 1 :]
                candidate_cost = route_cost(candidate, durations, return_to_start=return_to_start)
                if candidate_cost < best_cost - _MIN_IMPROVEMENT:
                    best, best_cost = candidate, candidate_cost
                    improved = True
    return best


# --------------------------------------------------------------------------------------------
# Google Maps
# --------------------------------------------------------------------------------------------


def _format_point(point: Point) -> str:
    lat, lon = point
    return f"{lat:.6f},{lon:.6f}"


def google_maps_url(
    start: Point, stops: Sequence[Point], mode: TravelMode, *, return_to_start: bool
) -> str:
    """Google Maps directions URL for the ordered stops.

    The route ends at the last stop, or back at the start when ``return_to_start`` is set.
    Values are percent-encoded (``,`` -> ``%2C``, ``|`` -> ``%7C``) as Google recommends.
    """
    if return_to_start or not stops:
        destination, waypoints = start, list(stops)
    else:
        destination, waypoints = stops[-1], list(stops[:-1])
    params = {
        "api": "1",
        "origin": _format_point(start),
        "destination": _format_point(destination),
    }
    if waypoints:
        params["waypoints"] = "|".join(_format_point(point) for point in waypoints)
    params["travelmode"] = GOOGLE_TRAVEL_MODES[mode]
    return f"{GOOGLE_MAPS_DIRECTIONS_URL}?{urlencode(params)}"


# --------------------------------------------------------------------------------------------
# Itinerary assembly
# --------------------------------------------------------------------------------------------


def _rounded(value: float) -> float:
    # 0.01 km is 10 m and 0.01 min under a second: plenty for display.
    return round(value, 2)


def _load_stores(db: Session, store_ids: Sequence[int]) -> list[Store]:
    """The stores in request order; raises ``UnknownStoresError`` listing every missing id."""
    found = {store.id: store for store in db.scalars(select(Store).where(Store.id.in_(store_ids)))}
    missing = [store_id for store_id in store_ids if store_id not in found]
    if missing:
        raise UnknownStoresError(missing)
    return [found[store_id] for store_id in store_ids]


def plan_itinerary(
    db: Session, user: User, request: schemas.ItineraryRequest, *, settings: Settings
) -> schemas.ItineraryResponse:
    """Load the stores (``UnknownStoresError`` on unknown ids), solve the order, build the response.

    ``travel_mode`` defaults to the user's preference. The road geometry is only requested when
    the OSRM matrix succeeded: if OSRM is down, a second call would just wait for another timeout.
    """
    stores = _load_stores(db, request.store_ids)
    mode = request.travel_mode or user.travel_mode
    start: Point = (request.start.lat, request.start.lon)
    points: list[Point] = [start, *((store.lat, store.lon) for store in stores)]

    with http_client() as client:
        matrix = travel_matrix(points, mode, settings=settings, client=client)
        order = solve_order(matrix.durations_min, return_to_start=request.return_to_start)
        path = [0, *order, 0] if request.return_to_start else [0, *order]
        geometry = (
            route_geometry([points[node] for node in path], mode, settings=settings, client=client)
            if matrix.source == "osrm"
            else None
        )

    durations, distances = matrix.durations_min, matrix.distances_km
    stops: list[schemas.ItineraryStop] = []
    elapsed_min = 0.0
    for position, (origin, node) in enumerate(pairwise([0, *order]), start=1):
        elapsed_min += durations[origin][node]
        store = stores[node - 1]
        stops.append(
            schemas.ItineraryStop(
                order=position,
                store=schemas.Store.from_model(
                    store, _rounded(haversine_km(*start, store.lat, store.lon))
                ),
                leg_distance_km=_rounded(distances[origin][node]),
                leg_duration_min=_rounded(durations[origin][node]),
                arrival_min=_rounded(elapsed_min),
            )
        )

    ordered_points = [points[node] for node in order]
    return schemas.ItineraryResponse(
        stops=stops,
        total_distance_km=_rounded(sum(distances[a][b] for a, b in pairwise(path))),
        total_duration_min=_rounded(
            route_cost(order, durations, return_to_start=request.return_to_start)
        ),
        geometry=geometry,
        routing_source=matrix.source,
        maps_url=google_maps_url(
            start, ordered_points, mode, return_to_start=request.return_to_start
        ),
    )
