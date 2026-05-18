"""API-EXT-03 国土交通省 不動産価格指数(賃料相場の代理).

reinfolib `XCT001`(不動産価格指数)を都道府県別に取得する.
住宅地・住宅・商業地の指数のうち、住宅向けの値を採用.

参照: https://www.reinfolib.mlit.go.jp/help/apiManual/
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
        if not self.api_key:
            logger.warning("REINFOLIB_API_KEY 未設定。rent_index fetch をスキップ(INV-EXT-001)")
            return

        headers = {"Ocp-Apim-Subscription-Key": self.api_key}
        for pref_int in range(1, 48):
            pref_code = f"{pref_int:02d}"
            try:
                payload = get_json(ENDPOINT_RENT_INDEX, params={"area": pref_int}, headers=headers)
            except HttpRetryExhausted:
                logger.exception(f"rent_index fetch failed for area={pref_int}")
                continue

            record = _latest_residential_index(payload)
            if record is None:
                continue
            yield {
                "indicator_id": "rent_index",
                "prefecture_code": pref_code,
                "value": record["value"],
                "measured_at": record.get("measured_at"),
            }

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
