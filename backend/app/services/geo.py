"""Geographic helpers: distances, bounding boxes and area cell keys (ARCHITECTURE.md section 3).

Longitudes are not wrapped across the antimeridian; ShopEx targets populated areas far from it.
"""

from __future__ import annotations

import math
from typing import NamedTuple

EARTH_RADIUS_KM = 6371.0088

# Area cache granularity: centres snap to a 0.05 degree grid (about 5.5 km north-south).
CELL_SIZE_DEG = 0.05
# A cached area must cover the requested radius, so radii round *up* to one of these buckets.
RADIUS_BUCKETS_KM: tuple[float, ...] = (1, 2, 5, 10, 15, 20, 30, 40, 50)
_LARGE_RADIUS_STEP_KM = 10


class BoundingBox(NamedTuple):
    min_lat: float
    min_lon: float
    max_lat: float
    max_lon: float

    def contains(self, lat: float, lon: float) -> bool:
        return self.min_lat <= lat <= self.max_lat and self.min_lon <= lon <= self.max_lon


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance between two points, in kilometres."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = phi2 - phi1
    d_lambda = math.radians(lon2 - lon1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(min(1.0, math.sqrt(a)))


def bounding_box(lat: float, lon: float, radius_km: float) -> BoundingBox:
    """Smallest lat/lon box containing the circle; use it to pre-filter on ``(lat, lon)``.

    Always confirm candidates with ``haversine_km``: box corners lie outside the circle.
    """
    if radius_km < 0:
        raise ValueError("radius_km must be non-negative")
    lat_delta = math.degrees(radius_km / EARTH_RADIUS_KM)
    # Near the poles a degree of longitude shrinks to nothing; cap the factor.
    cos_lat = max(math.cos(math.radians(lat)), 0.01)
    lon_delta = min(lat_delta / cos_lat, 180.0)
    return BoundingBox(
        min_lat=max(lat - lat_delta, -90.0),
        min_lon=max(lon - lon_delta, -180.0),
        max_lat=min(lat + lat_delta, 90.0),
        max_lon=min(lon + lon_delta, 180.0),
    )


def _snap(value: float) -> float:
    # "+ 0.0" turns -0.0 into 0.0 so keys never contain "-0.00".
    return round(round(value / CELL_SIZE_DEG) * CELL_SIZE_DEG, 2) + 0.0


def snap_to_cell(lat: float, lon: float) -> tuple[float, float]:
    """Centre of the grid cell containing the point."""
    return _snap(lat), _snap(lon)


def radius_bucket_km(radius_km: float) -> float:
    """Smallest bucket radius that covers ``radius_km``."""
    if radius_km <= 0:
        raise ValueError("radius_km must be positive")
    for bucket in RADIUS_BUCKETS_KM:
        if radius_km <= bucket:
            return float(bucket)
    return float(math.ceil(radius_km / _LARGE_RADIUS_STEP_KM) * _LARGE_RADIUS_STEP_KM)


def area_cell_key(lat: float, lon: float, radius_km: float) -> str:
    """Cache key of an area: snapped centre plus radius bucket, e.g. ``"45.50,-73.55/10km"``."""
    cell_lat, cell_lon = snap_to_cell(lat, lon)
    return f"{cell_lat:.2f},{cell_lon:.2f}/{radius_bucket_km(radius_km):g}km"
