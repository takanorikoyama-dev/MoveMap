"""API-EXT-03 国土交通省 賃料相場(代理指標) - 暫定無効化.

経緯(2026-05-19): reinfolib の `XCT001` を当初「不動産価格指数」と想定したが、
実 API 検証の結果、本エンドポイントは地価公示(標準地の単価)を返すことが判明.
賃料相場の代理として使うのは妥当性に欠けるため、適切な賃料統計の
エンドポイント特定までは fetch を skip する.

候補(後日検討):
    - e-Stat 住宅・土地統計調査(都道府県別 家賃の月額) の表 ID 特定
    - 不動産情報ライブラリの別エンドポイント
    - 民間: SUUMO / LIFULL HOME'S のリリースデータ
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from typing import Any

from app.features.data_pipeline.sources._base import DataSourceAdapter
from app.shared.http_client import HttpRetryExhausted, HttpSchemaError, get_json, head_last_modified
from app.shared.logger import get_logger

logger = get_logger(__name__)

REINFOLIB_BASE = "https://www.reinfolib.mlit.go.jp/ex-api/external"
ENDPOINT_RENT_INDEX = f"{REINFOLIB_BASE}/XCT001"


class MlitRentIndexAdapter(DataSourceAdapter):
    source_id = "mlit_rent_index"

    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key or os.getenv("REINFOLIB_API_KEY")

    def fetch(self) -> Iterator[dict[str, Any]]:
        # 暫定: 賃料の適切な API エンドポイントが特定できていないため skip.
        # 詳細はモジュール docstring を参照. INV-EXT-001 に従い空イテレータを返す.
        logger.warning("mlit_rent_index: 暫定無効化中(賃料 API 未特定)。dummy フォールバックに任せる")
        return
        yield  # noqa: B901  # unreachable, signature 維持のため

    def last_updated(self) -> str | None:
        return head_last_modified(ENDPOINT_RENT_INDEX)


def _latest_residential_index(payload: dict[str, Any]) -> dict[str, Any] | None:
    """payload から「住宅地」の最新月の指数を抽出する.

    レスポンス例:
      {"data": [{"YearMonth": "2024-06", "Type": "住宅地", "Index": 110.5}, ...]}
    """
    if not isinstance(payload, dict):
        raise HttpSchemaError("payload is not a dict")
    data = payload.get("data") or payload.get("Data") or []
    if not isinstance(data, list):
        raise HttpSchemaError("`data` field is not a list")

    residential = [item for item in data if str(item.get("Type", "")).startswith(("住宅", "Residential"))]
    if not residential:
        return None

    def _sort_key(item: dict[str, Any]) -> str:
        return str(item.get("YearMonth") or item.get("yearMonth") or "")

    latest = max(residential, key=_sort_key, default=None)
    if latest is None:
        return None
    try:
        value = float(latest.get("Index") or latest.get("index") or 0)
    except (TypeError, ValueError):
        return None
    ym = _sort_key(latest)
    measured_at = f"{ym}-01" if len(ym) == 7 and ym.count("-") == 1 else (ym or None)
    return {"value": value, "measured_at": measured_at}
