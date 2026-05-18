"""shared/geo.py の単体テスト."""

from __future__ import annotations

import math

from app.shared.geo import haversine_km, nearest_distance_km, prefecture_centroids


def test_haversine_zero_distance() -> None:
    assert haversine_km(35.0, 139.0, 35.0, 139.0) == 0.0


def test_haversine_tokyo_to_osaka_approx() -> None:
    """東京-大阪 は約 400km(±20km の許容)."""
    tokyo = (35.6895, 139.6917)
    osaka = (34.6863, 135.5199)
    d = haversine_km(tokyo[0], tokyo[1], osaka[0], osaka[1])
    assert 380 <= d <= 420


def test_nearest_distance_km_empty() -> None:
    assert math.isinf(nearest_distance_km(35.0, 139.0, []))


def test_nearest_distance_km_finds_min() -> None:
    points = [(40.0, 140.0), (35.5, 139.5), (30.0, 130.0)]
    # (35.5, 139.5) が最も近い
    d = nearest_distance_km(35.0, 139.0, points)
    assert d < 100


def test_prefecture_centroids_loads_47() -> None:
    centroids = prefecture_centroids()
    assert len(centroids) == 47
    assert "13" in centroids
    lat, lon = centroids["13"]
    assert 35 < lat < 36
    assert 139 < lon < 140
