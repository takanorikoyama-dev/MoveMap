"""API-EXT-05 国土地理院 ハザードマップポータル(災害リスク).

D-02: 災害リスクを「地震・津波・土砂・洪水」の 4 サブスコア + 合成 1 として算出.
GeoJSON ベースの空間データから都道府県重心を含むセルのリスクスコアを抽出して合成する.

Phase 7 段階: 公開オープンデータの所定 URL から、都道府県別事前集計済みスコア(seeds/hazard_scores.json 形式)
を読み込む方針.実 API 経由のリアルタイム取得は Phase 8 以降で検討.
"""

from __future__ import annotations

import json
import os
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from app.features.data_pipeline.sources._base import DataSourceAdapter
from app.shared.config import PROJECT_ROOT
from app.shared.http_client import HttpRetryExhausted, get_json, head_last_modified
from app.shared.logger import get_logger

logger = get_logger(__name__)

DEFAULT_HAZARD_SCORE_PATH = PROJECT_ROOT / "seeds" / "hazard_scores.json"
DEFAULT_HAZARD_SCORE_URL = "https://disaportal.gsi.go.jp/hazard_scores.json"  # 配信予定 URL 仮置き
SUB_HAZARDS = ("earthquake", "tsunami", "landslide", "flood")


class GsiHazardAdapter(DataSourceAdapter):
    """ハザードリスクスコアを都道府県別に提供する.

    優先順位:
        1. ローカル `seeds/hazard_scores.json` が存在すればそれを利用(オフライン対応)
        2. なければ `GSI_HAZARD_URL` の JSON を取得
        3. どちらも失敗時は空(INV-EXT-001 で前回値保持)
    """

    source_id = "gsi_hazard"

    def __init__(self, score_path: Path | None = None, score_url: str | None = None) -> None:
        self.score_path = score_path or DEFAULT_HAZARD_SCORE_PATH
        self.score_url = score_url or os.getenv("GSI_HAZARD_URL", DEFAULT_HAZARD_SCORE_URL)

    def fetch(self) -> Iterator[dict[str, Any]]:
        payload = self._load_local() or self._load_remote()
        if payload is None:
            return
        yield from _parse_hazard_payload(payload)

    def last_updated(self) -> str | None:
        if self.score_path.exists():
            from datetime import datetime, timezone

            return datetime.fromtimestamp(self.score_path.stat().st_mtime, tz=timezone.utc).isoformat()
        return head_last_modified(self.score_url)

    def _load_local(self) -> Any | None:
        if not self.score_path.exists():
            return None
        try:
            return json.loads(self.score_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            logger.exception(f"hazard local file parse failed: {self.score_path}")
            return None

    def _load_remote(self) -> Any | None:
        try:
            return get_json(self.score_url)
        except HttpRetryExhausted:
            logger.exception(f"hazard remote fetch failed: {self.score_url}")
            return None


def _parse_hazard_payload(payload: Any) -> Iterator[dict[str, Any]]:
    """ハザードスコア JSON を都道府県別レコードに変換.

    想定形式:
      {"01": {"earthquake": 3.2, "tsunami": 2.1, "landslide": 1.5, "flood": 2.0},
       "02": {...}, ...}
    合成スコア = 4 サブの平均.

    """
    if not isinstance(payload, dict):
        return

    for raw_code, scores in payload.items():
        if not isinstance(scores, dict):
            continue
        try:
            pref_code = f"{int(raw_code):02d}"
        except (TypeError, ValueError):
            continue
        if not (1 <= int(pref_code) <= 47):
            continue

        values: list[float] = []
        for key in SUB_HAZARDS:
            try:
                values.append(float(scores.get(key, 0)))
            except (TypeError, ValueError):
                continue

        if not values:
            continue
        combined = sum(values) / len(values)
        yield {
            "indicator_id": "disaster_risk",
            "prefecture_code": pref_code,
            "value": combined,
            "measured_at": None,  # JSON 側で provide される場合に拡張
        }
