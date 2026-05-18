"""API-EXT-02 国土交通省 地価(不動産取引価格情報).

reinfolib(不動産情報ライブラリ)の `XIT001` 不動産取引価格情報エンドポイントを利用.
都道府県別の取引データから単価平均(JPY/m²)を算出する.

実 API 検証(2026-05-19)で判明した仕様:
    - 必須パラメータ: `year`(取引年 4桁、2024 等). 未指定だと 400.
    - 応答キー: `TradePrice`(取引価格 円), `Area`(面積 m²), `UnitPrice`(土地単価),
      `PricePerUnit`(1m²あたり単価別形式), `Period`(`2024年第1四半期` 等)
    - 1 都道府県あたり数万件返るため、集計後の単価平均だけを yield する.

参照: https://www.reinfolib.mlit.go.jp/help/apiManual/
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


DEFAULT_YEAR = 2024


class MlitLandPriceAdapter(DataSourceAdapter):
    source_id = "mlit_land_price"

    def __init__(self, api_key: str | None = None, year: int | None = None) -> None:
        self.api_key = api_key or os.getenv("REINFOLIB_API_KEY")
        self.year = year if year is not None else DEFAULT_YEAR

    def fetch(self) -> Iterator[dict[str, Any]]:
        """全 47 都道府県の取引データから単価平均(JPY/m²)を yield する."""
        if not self.api_key:
            logger.warning("REINFOLIB_API_KEY 未設定。data 取得をスキップ(INV-EXT-001)")
            return

        headers = {"Ocp-Apim-Subscription-Key": self.api_key}
        sums: dict[str, float] = defaultdict(float)
        counts: dict[str, int] = defaultdict(int)
        latest_date: str | None = None

        for pref_int in range(1, 48):
            pref_code = f"{pref_int:02d}"
            # area は 2 桁ゼロパディング文字列(整数だと 400 'area の形式が不正')
            params: dict[str, Any] = {"year": self.year, "area": pref_code}
            try:
                payload = get_json(ENDPOINT_LAND_PRICE, params=params, headers=headers)
            except HttpRetryExhausted:
                logger.exception(f"land_price fetch failed for area={pref_code}")
                continue

            for record in _parse_land_price_records(payload):
                price = record.get("price_per_sqm")
                if price is None or price <= 0:
                    continue
                sums[pref_code] += price
                counts[pref_code] += 1
                if measured := record.get("measured_at"):
                    latest_date = max(latest_date, measured) if latest_date else measured

            logger.info(f"land_price fetched: pref={pref_code} accumulated={counts[pref_code]}")

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
    """reinfolib XIT001(不動産取引価格情報)レスポンスから単価(JPY/m²)を yield.

    実 API レスポンス構造(2026-05-19 検証):
        {"status": "OK", "data": [
            {"PriceCategory": "不動産取引価格情報", "Type": "中古マンション等",
             "TradePrice": "140000000", "PricePerUnit": "", "Area": "90",
             "UnitPrice": "", "Period": "2024年第1四半期", ...},
            ...
        ]}

    単価の決め方(優先順):
        1. `UnitPrice`(土地の単価が直接入っているケース)
        2. `PricePerUnit`(同上、別形式)
        3. `TradePrice` / `Area`(建物含む不動産の場合の単価算出)
    """
    if not isinstance(payload, dict):
        raise HttpSchemaError("payload is not a dict")
    data = payload.get("data") or payload.get("Data") or []
    if not isinstance(data, list):
        raise HttpSchemaError("`data` field is not a list")
    for item in data:
        unit_price = _extract_unit_price(item)
        if unit_price is None or unit_price <= 0:
            continue
        measured_at = _period_to_iso(item.get("Period"))
        yield {"price_per_sqm": unit_price, "measured_at": measured_at}


def _to_float(value: Any) -> float | None:
    """カンマ・空文字を除いた float 変換、不可なら None."""
    if value is None:
        return None
    s = str(value).replace(",", "").strip()
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _extract_unit_price(item: dict[str, Any]) -> float | None:
    """1 取引レコードから JPY/m² 単価を抽出."""
    for key in ("UnitPrice", "PricePerUnit"):
        unit = _to_float(item.get(key))
        if unit is not None and unit > 0:
            return unit
    trade = _to_float(item.get("TradePrice"))
    area = _to_float(item.get("Area"))
    if trade is not None and trade > 0 and area is not None and area > 0:
        return trade / area
    return None


def _period_to_iso(period: Any) -> str | None:
    """`'2024年第1四半期'` → `'2024-01-01'` の年抽出."""
    if not isinstance(period, str):
        return None
    digits = "".join(c for c in period[:4] if c.isdigit())
    if len(digits) != 4:
        return None
    return f"{digits}-01-01"
