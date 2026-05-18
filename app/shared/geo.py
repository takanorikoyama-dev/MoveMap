"""地理計算ヘルパー(haversine 距離・都道府県重心ロード)."""

from __future__ import annotations

import csv
import math
from functools import lru_cache

from app.shared.config import PROJECT_ROOT

EARTH_RADIUS_KM = 6371.0


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """2 点間の大円距離(km)を返す."""
    rlat1, rlat2 = math.radians(lat1), math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(rlat1) * math.cos(rlat2) * math.sin(dlon / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return EARTH_RADIUS_KM * c


@lru_cache(maxsize=1)
def prefecture_centroids() -> dict[str, tuple[float, float]]:
    """seeds/prefectures.csv から {code: (lat, lon)} を返す."""
    path = PROJECT_ROOT / "seeds" / "prefectures.csv"
    centroids: dict[str, tuple[float, float]] = {}
    with path.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            centroids[r["code"]] = (float(r["centroid_lat"]), float(r["centroid_lon"]))
    return centroids


def nearest_distance_km(target_lat: float, target_lon: float, points: list[tuple[float, float]]) -> float:
    """target からの最短 km 距離を返す.points が空なら inf."""
    if not points:
        return math.inf
    return min(haversine_km(target_lat, target_lon, lat, lon) for lat, lon in points)
