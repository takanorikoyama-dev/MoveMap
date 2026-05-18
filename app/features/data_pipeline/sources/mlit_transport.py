"""API-EXT-06 国土交通省 交通インフラデータ(交通アクセス).

各都道府県の重心から最寄りの空港・新幹線駅・高速 IC までの距離(km)を計算し、
正規化スコア(0〜5、5 が最良)として返す.

データ源:
  - 国土交通省 国土数値情報(配信形式: CSV / Shapefile)
  - Phase 7 段階: ローカル `seeds/transport_facilities.json` を使用(キー: airports/shinkansen/ic、値は [lat, lon] のリスト)
  - 実 API 取得は Phase 8 以降で検討.
"""

from __future__ import annotations

import json
import math
import os
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from app.features.data_pipeline.sources._base import DataSourceAdapter
from app.shared.config import PROJECT_ROOT
from app.shared.geo import nearest_distance_km, prefecture_centroids
from app.shared.http_client import HttpRetryExhausted, get_json, head_last_modified
from app.shared.logger import get_logger

logger = get_logger(__name__)

DEFAULT_FACILITIES_PATH = PROJECT_ROOT / "seeds" / "transport_facilities.json"
DEFAULT_FACILITIES_URL = "https://www.mlit.go.jp/sogoseisaku/transport/movemap_facilities.json"  # 仮置き

# 各カテゴリの重み(交通アクセスの「総合スコア」算出時)
CATEGORY_WEIGHTS: dict[str, float] = {
    "airport": 0.4,
    "shinkansen": 0.4,
    "ic": 0.2,
}

# 距離スコアの基準値(km).基準以下なら満点(5)、 reference の 4 倍なら 1 点に減衰.
REFERENCE_KM: dict[str, float] = {
    "airport": 50.0,
    "shinkansen": 30.0,
    "ic": 10.0,
}


class MlitTransportAdapter(DataSourceAdapter):
    source_id = "mlit_transport"

    def __init__(self, facilities_path: Path | None = None, facilities_url: str | None = None) -> None:
        self.facilities_path = facilities_path or DEFAULT_FACILITIES_PATH
        self.facilities_url = facilities_url or os.getenv("MLIT_TRANSPORT_URL", DEFAULT_FACILITIES_URL)

    def fetch(self) -> Iterator[dict[str, Any]]:
        facilities = self._load_local() or self._load_remote()
        if facilities is None:
            return

        airports = _as_points(facilities.get("airports"))
        shinkansen = _as_points(facilities.get("shinkansen"))
        ic = _as_points(facilities.get("ic"))

        for pref_code, (lat, lon) in prefecture_centroids().items():
            score = _aggregate_score(
                lat,
                lon,
                {"airport": airports, "shinkansen": shinkansen, "ic": ic},
            )
            yield {
                "indicator_id": "transport_access",
                "prefecture_code": pref_code,
                "value": score,
                "measured_at": None,
            }

    def last_updated(self) -> str | None:
        if self.facilities_path.exists():
            from datetime import datetime, timezone

            return datetime.fromtimestamp(self.facilities_path.stat().st_mtime, tz=timezone.utc).isoformat()
        return head_last_modified(self.facilities_url)

    def _load_local(self) -> Any | None:
        if not self.facilities_path.exists():
            return None
        try:
            return json.loads(self.facilities_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            logger.exception(f"transport local file parse failed: {self.facilities_path}")
            return None

    def _load_remote(self) -> Any | None:
        try:
            return get_json(self.facilities_url)
        except HttpRetryExhausted:
            logger.exception(f"transport remote fetch failed: {self.facilities_url}")
            return None


def _as_points(raw: Any) -> list[tuple[float, float]]:
    if not isinstance(raw, list):
        return []
    points: list[tuple[float, float]] = []
    for item in raw:
        if isinstance(item, (list, tuple)) and len(item) == 2:
            try:
                points.append((float(item[0]), float(item[1])))
            except (TypeError, ValueError):
                continue
        elif isinstance(item, dict):
            try:
                points.append((float(item["lat"]), float(item["lon"])))
            except (KeyError, TypeError, ValueError):
                continue
    return points


def _distance_score(distance_km: float, reference_km: float) -> float:
    """0(遠い)〜5(近い)の連続スコア."""
    if math.isinf(distance_km):
        return 0.0
    if distance_km <= reference_km:
        return 5.0
    # 線形減衰: ref で 5、 4*ref で 1、それ以上は 1 に張り付き
    decay = 5.0 - 4.0 * (distance_km - reference_km) / (3 * reference_km)
    return max(1.0, decay)


def _aggregate_score(
    pref_lat: float,
    pref_lon: float,
    categories: dict[str, list[tuple[float, float]]],
) -> float:
    total = 0.0
    weight_sum = 0.0
    for category, points in categories.items():
        dist = nearest_distance_km(pref_lat, pref_lon, points)
        score = _distance_score(dist, REFERENCE_KM[category])
        weight = CATEGORY_WEIGHTS[category]
        total += score * weight
        weight_sum += weight
    return total / weight_sum if weight_sum > 0 else 0.0
