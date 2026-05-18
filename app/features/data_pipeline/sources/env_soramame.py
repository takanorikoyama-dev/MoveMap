"""API-EXT-04 空気質(PM2.5).

source_id = 'env_soramame' のままだが、実装は WAQI(World Air Quality Index)を使用.

経緯:
    当初は環境省「そらまめ君」の JSON 配信を想定していたが、配信形式が変更され
    `https://soramame.env.go.jp/data/map/kyokuChoshi/pm25.json` は HTML を返す
    ようになった(2026-05-18 検証). 代替として WAQI を採用.
    source_id は DB の data_sources レコードと整合するため変更しない.

仕様:
    各都道府県の重心(緯度経度)から WAQI `feed/geo:{lat};{lon}/?token=...` を叩き、
    `data.iaqi.pm25.v` を採用. 取得不可なら `data.aqi`(0-500) で代用.

参照:
    https://aqicn.org/json-api/doc/
    Token 取得: https://aqicn.org/data-platform/token/(無料)
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from app.features.data_pipeline.sources._base import DataSourceAdapter
from app.shared.config import load_config
from app.shared.geo import prefecture_centroids
from app.shared.http_client import HttpRetryExhausted, HttpSchemaError, get_json, head_last_modified
from app.shared.logger import get_logger

logger = get_logger(__name__)

WAQI_FEED_URL = "https://api.waqi.info/feed/geo:{lat};{lon}/"


class SoramameAdapter(DataSourceAdapter):
    """空気質(PM2.5)アダプタ. 内部実装は WAQI."""

    source_id = "env_soramame"

    def __init__(self, token: str | None = None) -> None:
        config = load_config()
        self.token = token if token is not None else config.waqi_token

    def fetch(self) -> Iterator[dict[str, Any]]:
        if not self.token:
            logger.warning("WAQI_TOKEN 未設定。air_quality fetch をスキップ(INV-EXT-001)")
            return

        for pref_code, (lat, lon) in prefecture_centroids().items():
            try:
                payload = get_json(
                    WAQI_FEED_URL.format(lat=lat, lon=lon),
                    params={"token": self.token},
                )
            except HttpRetryExhausted:
                logger.exception(f"WAQI fetch failed for pref={pref_code}")
                continue
            except HttpSchemaError:
                logger.exception(f"WAQI schema error for pref={pref_code}")
                continue

            record = _parse_waqi_feed(pref_code, payload)
            if record is not None:
                yield record

    def last_updated(self) -> str | None:
        # WAQI は station ごとに更新時刻が異なるため、HEAD で全体時刻は取得不可
        return head_last_modified("https://api.waqi.info/")


def _parse_waqi_feed(pref_code: str, payload: dict[str, Any]) -> dict[str, Any] | None:
    """WAQI のレスポンスから PM2.5 値を抽出.

    レスポンス例:
        {"status": "ok", "data": {
            "aqi": 55, "idx": 12345,
            "iaqi": {"pm25": {"v": 18.5}, "pm10": {"v": 25.0}, ...},
            "time": {"s": "2026-05-18 09:00:00", "iso": "..."},
            "city": {"name": "Tokyo, Japan", "geo": [35.68, 139.69]}
        }}

    Returns:
        正規化前レコード or None(取得不可).
    """
    if not isinstance(payload, dict):
        return None
    if payload.get("status") != "ok":
        return None
    data = payload.get("data")
    if not isinstance(data, dict):
        return None

    # PM2.5 を優先採用、無ければ AQI で代用
    iaqi = data.get("iaqi") or {}
    value: float | None = None
    if isinstance(iaqi, dict):
        pm25 = iaqi.get("pm25")
        if isinstance(pm25, dict) and isinstance(pm25.get("v"), (int, float)):
            value = float(pm25["v"])
    if value is None:
        aqi = data.get("aqi")
        if isinstance(aqi, (int, float)):
            value = float(aqi)
    if value is None or value < 0:
        return None

    time_info = data.get("time")
    measured_at: str | None = None
    if isinstance(time_info, dict):
        iso = time_info.get("iso") or time_info.get("s")
        if isinstance(iso, str) and len(iso) >= 10:
            measured_at = iso[:10]

    return {
        "indicator_id": "air_quality",
        "prefecture_code": pref_code,
        "value": value,
        "measured_at": measured_at,
    }
