"""Distances, bounding boxes and area cell keys."""

import pytest

from app.services.geo import (
    area_cell_key,
    bounding_box,
    haversine_km,
    radius_bucket_km,
    snap_to_cell,
)

MONTREAL = (45.5017, -73.5673)
QUEBEC_CITY = (46.8139, -71.2080)


def test_haversine_matches_known_distance() -> None:
    assert haversine_km(*MONTREAL, *QUEBEC_CITY) == pytest.approx(233.4, rel=0.01)
    assert haversine_km(*MONTREAL, *MONTREAL) == 0


def test_bounding_box_contains_the_whole_circle() -> None:
    radius_km = 10
    box = bounding_box(*MONTREAL, radius_km)

    for lat, lon in [(box.min_lat, MONTREAL[1]), (MONTREAL[0], box.max_lon)]:
        assert haversine_km(*MONTREAL, lat, lon) == pytest.approx(radius_km, rel=0.01)
    assert box.contains(*MONTREAL)
    assert not box.contains(*QUEBEC_CITY)


def test_bounding_box_is_clamped_near_the_poles() -> None:
    box = bounding_box(89.99, 0, 50)

    assert box.max_lat == 90
    assert box.min_lon >= -180
    assert box.max_lon <= 180


def test_bounding_box_rejects_negative_radius() -> None:
    with pytest.raises(ValueError, match="radius_km"):
        bounding_box(0, 0, -1)


def test_snap_to_cell_uses_a_005_degree_grid() -> None:
    assert snap_to_cell(*MONTREAL) == (45.5, -73.55)
    assert snap_to_cell(-0.01, 0.024) == (0.0, 0.0)


@pytest.mark.parametrize(
    ("radius", "bucket"), [(0.5, 1), (3, 5), (10, 10), (10.1, 15), (50, 50), (51, 60)]
)
def test_radius_bucket_rounds_up(radius: float, bucket: float) -> None:
    assert radius_bucket_km(radius) == bucket


def test_radius_bucket_rejects_non_positive_radius() -> None:
    with pytest.raises(ValueError, match="radius_km"):
        radius_bucket_km(0)


def test_area_cell_key_is_stable_for_nearby_points() -> None:
    assert area_cell_key(*MONTREAL, 10) == "45.50,-73.55/10km"
    assert area_cell_key(45.51, -73.56, 8) == area_cell_key(*MONTREAL, 10)
    assert area_cell_key(-0.001, -0.001, 2) == "0.00,0.00/2km"
