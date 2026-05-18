"""API-EXT-02 国土交通省 地価公示.

reinfolib(不動産情報ライブラリ)の `XIT001`(地価公示・地価調査)エンドポイントを利用.
レスポンス JSON から都道府県別の単価平均(JPY/m²)を算出する.

参照: https://www.reinfolib.mlit.go.jp/help/apiManual/
注意: API キーが必要な場合あり(reinfolib に登録. 環境変数 `REINFOLIB_API_KEY`).
"""

from __future__ import annotations

import os
from collections import defaultdict
from collections.abc import Iterator
from typing import Any

from app.features.data_pipeline.sources._base import DataSourceAdapter
from app.shared.http_client import HttpRetryExhausted, HttpSchemaError, get_json, head_last_modified
from app.shared.logger import get_logger

logger = get_logger(__name__)

REINFOLIB_BASE = "https://www.reinfolib.mlit.go.jp/ex-api/external"
ENDPOINT_LAND_PRICE = f"{REINFOLIB_BASE}/XIT001"


class MlitLandPriceAdapter(DataSourceAdapter):
    source_id = "mlit_land_price"

    def __init__(self, api_key: str | None = None, year: int | None = None) -> None:
        self.api_key = api_key or os.getenv("REINFOLIB_API_KEY")
        self.year = year  # 取得対象年。None なら最新

    def fetch(self) -> Iterator[dict[str, Any]]:
        """全 47 都道府県の地価公示データを取得し、都道府県別単価平均を yield する."""
        if not self.api_key:
            logger.warning("REINFOLIB_API_KEY 未設定。data 取得をスキップ(INV-EXT-001)")
            return

        headers = {"Ocp-Apim-Subscription-Key": self.api_key}
        sums: dict[str, float] = defaultdict(float)
        counts: dict[str, int] = defaultdict(int)
        latest_date: str | None = None

        for pref_int in range(1, 48):
            pref_code = f"{pref_int:02d}"
            params: dict[str, Any] = {"area": pref_int}
            if self.year is not None:
                params["year"] = self.year
            try:
                payload = get_json(ENDPOINT_LAND_PRICE, params=params, headers=headers)
            except HttpRetryExhausted:
                logger.exception(f"land_price fetch failed for area={pref_int}")
                continue

            for record in _parse_land_price_records(payload):
                price = record.get("price_per_sqm")
                if price is None or price <= 0:
                    continue
                sums[pref_code] += price
                counts[pref_code] += 1
                if measured := record.get("measured_at"):
                    latest_date = max(latest_date, measured) if latest_date else measured

        for code, total in sums.items():
            count = counts[code]
            if count == 0:
                continue
            yield {
                "indicator_id": "land_price",
                "prefecture_code": code,
                "value": total / count,
                "measured_at": latest_date,
            }

    def last_updated(self) -> str | None:
        return head_last_modified(ENDPOINT_LAND_PRICE)


def _parse_land_price_records(payload: dict[str, Any]) -> Iterator[dict[str, Any]]:
    """reinfolib のレスポンスから (単価, 計測日) を yield する.

    レスポンス JSON 構造:
      {"status": "OK", "data": [{"PrefectureCode": "13", "Year": 2024,
                                "Price": "350000", "Area": "100", ...}, ...]}
    `Price` は対象不動産の総価格(円)、 `Area` は m²。単価 = Price / Area で算出.

    """
    if not isinstance(payload, dict):
        raise HttpSchemaError("payload is not a dict")
    data = payload.get("data") or payload.get("Data") or []
    if not isinstance(data, list):
        raise HttpSchemaError("`data` field is not a list")
    for item in data:
        try:
            price = float(str(item.get("Price", "")).replace(",", ""))
            area = float(str(item.get("Area", "")).replace(",", ""))
        except ValueError:
            continue
        if area <= 0:
            continue
        unit_price = price / area
        year = item.get("Year")
        measured_at = f"{year}-01-01" if isinstance(year, int) else None
        yield {"price_per_sqm": unit_price, "measured_at": measured_at}
