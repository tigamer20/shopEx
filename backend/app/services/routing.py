"""Travel times between points: OSRM client with a straight-line estimate fallback.

Implements ARCHITECTURE.md section 4 "Itinerary": OSRM ``/table/v1/{profile}`` for the matrix
and ``/route`` (``overview=full&geometries=geojson``) for the geometry; on failure or timeout the
matrix is estimated as haversine x 1.3 detour at 35 km/h (driving), 15 (cycling), 5 (walking).

OSRM speaks ``lon,lat`` while the rest of ShopEx uses ``(lat, lon)``; the conversion happens
only in this module.
"""

from __future__ import annotations

import logging
import math
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any

import httpx

from app import __version__
from app.config import Settings
from app.schemas import RoutingSource, TravelMode
from app.services.geo import haversine_km

logger = logging.getLogger(__name__)

# (lat, lon)
Point = tuple[float, float]

# Profile names of the stock OSRM Lua profiles (car.lua, foot.lua, bicycle.lua).
OSRM_PROFILES: dict[TravelMode, str] = {"driving": "car", "walking": "foot", "cycling": "bike"}

# Straight-line estimate: roads are about 30 % longer than the crow flies.
DETOUR_FACTOR = 1.3
ESTIMATE_SPEED_KMH: dict[TravelMode, float] = {"driving": 35.0, "cycling": 15.0, "walking": 5.0}

USER_AGENT = f"ShopEx/{__version__}"
# Literal query strings: OSRM expects the raw "," and httpx would percent-encode it as a param.
_TABLE_QUERY = "annotations=duration,distance"
_ROUTE_QUERY = "overview=full&geometries=geojson"
# Six decimals is about 0.1 m, well below GPS accuracy.
_COORDINATE_DECIMALS = 6


class OsrmResponseError(Exception):
    """OSRM answered, but not with something usable."""


@dataclass(frozen=True, slots=True)
class TravelMatrix:
    """Square matrices indexed like the input points."""

    durations_min: list[list[float]]
    distances_km: list[list[float]]
    source: RoutingSource


def estimate_matrix(points: Sequence[Point], mode: TravelMode) -> TravelMatrix:
    """Straight-line estimate (``source="estimate"``); never fails."""
    speed_kmh = ESTIMATE_SPEED_KMH[mode]
    distances_km = [
        [DETOUR_FACTOR * haversine_km(*origin, *destination) for destination in points]
        for origin in points
    ]
    durations_min = [[distance / speed_kmh * 60 for distance in row] for row in distances_km]
    return TravelMatrix(durations_min=durations_min, distances_km=distances_km, source="estimate")


@contextmanager
def http_client(client: httpx.Client | None = None) -> Iterator[httpx.Client]:
    """Yield ``client`` unchanged, or a short-lived client that is closed on exit.

    Lets a caller share one connection pool between ``travel_matrix`` and ``route_geometry``.
    """
    if client is not None:
        yield client
        return
    with httpx.Client() as owned_client:
        yield owned_client


def travel_matrix(
    points: Sequence[Point],
    mode: TravelMode,
    *,
    settings: Settings,
    client: httpx.Client | None = None,
) -> TravelMatrix:
    """OSRM table when reachable (``source="osrm"``), else ``estimate_matrix``.

    Pairs OSRM cannot route (``null`` cells) and a missing distance matrix are filled in from the
    estimate, so the result always has the same shape as the input.
    """
    estimate = estimate_matrix(points, mode)
    if len(points) < 2:
        return estimate
    try:
        with http_client(client) as http:
            payload = _get_osrm(http, "table", points, mode, _TABLE_QUERY, settings)
        durations_s = _parse_matrix(payload.get("durations"), len(points), "durations")
        raw_distances = payload.get("distances")
        distances_m = (
            None
            if raw_distances is None
            else _parse_matrix(raw_distances, len(points), "distances")
        )
    except (httpx.HTTPError, OsrmResponseError) as exc:
        logger.warning(
            "OSRM table unavailable (%s); using the straight-line estimate", type(exc).__name__
        )
        return estimate

    durations_min = _merge(durations_s, estimate.durations_min, scale=1 / 60)
    distances_km = (
        estimate.distances_km
        if distances_m is None
        else _merge(distances_m, estimate.distances_km, scale=1 / 1000)
    )
    return TravelMatrix(durations_min=durations_min, distances_km=distances_km, source="osrm")


def route_geometry(
    points: Sequence[Point],
    mode: TravelMode,
    *,
    settings: Settings,
    client: httpx.Client | None = None,
) -> list[Point] | None:
    """Road geometry through ``points`` in order as ``[lat, lon]`` pairs; None on failure."""
    if len(points) < 2:
        return None
    try:
        with http_client(client) as http:
            payload = _get_osrm(http, "route", points, mode, _ROUTE_QUERY, settings)
        return _parse_route_geometry(payload)
    except (httpx.HTTPError, OsrmResponseError) as exc:
        logger.warning("OSRM route unavailable (%s); no geometry", type(exc).__name__)
        return None


# --------------------------------------------------------------------------------------------
# OSRM request and response helpers
# --------------------------------------------------------------------------------------------


def _format_coordinates(points: Sequence[Point]) -> str:
    """OSRM coordinate list: ``lon,lat;lon,lat;...`` in fixed-point notation."""
    parts: list[str] = []
    for lat, lon in points:
        if not (math.isfinite(lat) and math.isfinite(lon)):
            raise ValueError("coordinates must be finite numbers")
        parts.append(f"{lon:.{_COORDINATE_DECIMALS}f},{lat:.{_COORDINATE_DECIMALS}f}")
    return ";".join(parts)


def _get_osrm(
    client: httpx.Client,
    service: str,
    points: Sequence[Point],
    mode: TravelMode,
    query: str,
    settings: Settings,
) -> dict[str, Any]:
    """GET ``{OSRM_URL}/{service}/v1/{profile}/{coordinates}?{query}``; return the JSON object.

    Raises ``httpx.HTTPError`` (unreachable, timeout, non-2xx) or ``OsrmResponseError``.
    """
    base_url = settings.osrm_url.rstrip("/")
    coordinates = _format_coordinates(points)
    url = f"{base_url}/{service}/v1/{OSRM_PROFILES[mode]}/{coordinates}?{query}"
    response = client.get(
        url,
        headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
        timeout=settings.http_timeout_s,
    )
    response.raise_for_status()
    try:
        payload = response.json()
    except ValueError as exc:
        raise OsrmResponseError("response is not JSON") from exc
    if not isinstance(payload, dict):
        raise OsrmResponseError("response is not a JSON object")
    if payload.get("code") != "Ok":
        raise OsrmResponseError(f"OSRM code {payload.get('code')!r}")
    return payload


def _is_number(value: Any) -> bool:
    # bool is an int subclass; JSON true/false is never a valid travel time.
    return isinstance(value, int | float) and not isinstance(value, bool)


def _parse_matrix(raw: Any, size: int, name: str) -> list[list[float | None]]:
    """Validate an OSRM ``size`` x ``size`` matrix; ``None`` marks an unroutable pair."""
    if not isinstance(raw, list) or len(raw) != size:
        raise OsrmResponseError(f"{name} is not a {size}x{size} matrix")
    matrix: list[list[float | None]] = []
    for row in raw:
        if not isinstance(row, list) or len(row) != size:
            raise OsrmResponseError(f"{name} is not a {size}x{size} matrix")
        parsed_row: list[float | None] = []
        for value in row:
            if value is None:
                parsed_row.append(None)
            elif _is_number(value) and math.isfinite(value) and value >= 0:
                parsed_row.append(float(value))
            else:
                raise OsrmResponseError(f"{name} contains an invalid value")
        matrix.append(parsed_row)
    return matrix


def _merge(
    raw: list[list[float | None]], fallback: list[list[float]], *, scale: float
) -> list[list[float]]:
    """Scale OSRM values to ShopEx units, using ``fallback`` where OSRM found no route."""
    return [
        [
            fallback_value if value is None else value * scale
            for value, fallback_value in zip(row, fallback_row, strict=True)
        ]
        for row, fallback_row in zip(raw, fallback, strict=True)
    ]


def _parse_route_geometry(payload: dict[str, Any]) -> list[Point]:
    """``routes[0].geometry.coordinates`` (GeoJSON ``[lon, lat]``) as ``(lat, lon)`` points."""
    routes = payload.get("routes")
    if not isinstance(routes, list) or not routes or not isinstance(routes[0], dict):
        raise OsrmResponseError("no route")
    geometry = routes[0].get("geometry")
    coordinates = geometry.get("coordinates") if isinstance(geometry, dict) else None
    if not isinstance(coordinates, list) or len(coordinates) < 2:
        raise OsrmResponseError("route geometry is missing")

    points: list[Point] = []
    for position in coordinates:
        if not isinstance(position, list) or len(position) < 2:
            raise OsrmResponseError("route geometry contains an invalid position")
        lon, lat = position[0], position[1]
        if not (_is_number(lat) and _is_number(lon)):
            raise OsrmResponseError("route geometry contains an invalid position")
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            raise OsrmResponseError("route geometry contains an out-of-range position")
        points.append((float(lat), float(lon)))
    return points
