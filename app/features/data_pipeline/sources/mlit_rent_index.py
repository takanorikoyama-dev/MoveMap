"""API-EXT-03 賃料相場(都道府県別平均家賃, JPY/月).

source_id = 'mlit_rent_index' のままだが、実装は e-Stat の
**令和5年 住宅・土地統計調査 統計表 0004021429** を利用する.

経緯(2026-05-19):
    当初は reinfolib XCT001 を「不動産価格指数(賃料代理)」として想定したが、
    実 API では地価公示の標準地データを返すことが判明. その後 CPI 民営家賃
    (0003143513 cat01=0047) を試したが、本表の家賃サブ分類は東京都区部+全国
    の月次のみで都道府県別データを持たないことが判明.
    最終的に住宅・土地統計調査(5年に1回, 都道府県別の家賃階級×借家数)を
    採用. 階級代表値で加重平均して "平均家賃(円/月)" を算出.

参照: https://www.e-stat.go.jp/stat-search/files?stat_infid=000040262069
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterator
from typing import Any

from app.features.data_pipeline.sources._base import DataSourceAdapter
from app.shared.config import load_config
from app.shared.http_client import HttpRetryExhausted, HttpSchemaError, get_json, head_last_modified
from app.shared.logger import get_logger

logger = get_logger(__name__)

GET_STATS_DATA = "https://api.e-stat.go.jp/rest/3.0/app/json/getStatsData"
RENT_STATS_DATA_ID = "0004021429"

# cat03 = 住宅の１か月当たり家賃 コード → 階級代表値(円/月).
# 「200,000円以上」は階級上限が無いため、保守的に 225,000 を採用.
# 「不詳」「総数」「0円」は加重平均の対象外(0円は無料公営住宅等で平均から除外).
RENT_CLASS_MIDPOINT: dict[str, float] = {
    "02": 2_500.0,    # 1〜5,000円未満
    "03": 7_500.0,    # 5,000〜10,000円未満
    "04": 12_500.0,
    "05": 17_500.0,
    "06": 22_500.0,
    "07": 27_500.0,
    "08": 35_000.0,
    "09": 45_000.0,
    "10": 55_000.0,
    "11": 65_000.0,
    "12": 75_000.0,
    "13": 85_000.0,
    "14": 95_000.0,
    "15": 105_000.0,
    "16": 115_000.0,
    "17": 135_000.0,
    "18": 175_000.0,
    "19": 225_000.0,  # 200,000円以上の代表値(上限不明のため保守的に)
}


class MlitRentIndexAdapter(DataSourceAdapter):
    """賃料相場アダプタ. e-Stat 住宅・土地統計調査の家賃階級×借家数を加重平均."""

    source_id = "mlit_rent_index"

    def __init__(self, app_id: str | None = None) -> None:
        config = load_config()
        self.app_id = app_id if app_id is not None else config.estat_app_id

    def fetch(self) -> Iterator[dict[str, Any]]:
        """全 47 都道府県の平均家賃(円/月)を yield."""
        if not self.app_id:
            logger.warning("ESTAT_APP_ID 未設定。rent_index fetch をスキップ(INV-EXT-001)")
            return

        # cat01=0(住宅種別:総数), cat02=00(入居時期:総数), cat04=0(畳数:総数)で絞る
        # cat03(家賃階級) と area(都道府県) は集約せず全件取得
        params = {
            "appId": self.app_id,
            "statsDataId": RENT_STATS_DATA_ID,
            "cdCat01": "0",
            "cdCat02": "00",
            "cdCat04": "0",
            "metaGetFlg": "N",
            "cntGetFlg": "N",
            "explanationGetFlg": "N",
            "annotationGetFlg": "N",
            "limit": 5000,
        }
        try:
            payload = get_json(GET_STATS_DATA, params=params)
        except HttpRetryExhausted:
            logger.exception("e-Stat rent fetch failed")
            return

        yield from _aggregate_weighted_rent(payload)

    def last_updated(self) -> str | None:
        return head_last_modified("https://api.e-stat.go.jp/")


def _aggregate_weighted_rent(payload: dict[str, Any]) -> Iterator[dict[str, Any]]:
    """e-Stat レスポンスから都道府県別の加重平均家賃を算出.

    各都道府県 × 家賃階級 → 戸数 を集計し、階級代表値(RENT_CLASS_MIDPOINT)で
    加重平均: 平均家賃 = Σ(代表値 × 戸数) / Σ(戸数).

    "0円"(code=01), "不詳"(code=99), "総数"(code=00) は除外.
    """
    try:
        values = payload["GET_STATS_DATA"]["STATISTICAL_DATA"]["DATA_INF"]["VALUE"]
        if not isinstance(values, list):
            values = [values]
    except (KeyError, TypeError) as exc:
        raise HttpSchemaError("e-Stat rent payload shape unexpected") from exc

    # pref_code → weighted_sum / total_count
    weighted_sum: dict[str, float] = defaultdict(float)
    total_count: dict[str, float] = defaultdict(float)
    measured_at: str | None = None

    for v in values:
        area = v.get("@area", "")
        cat03 = v.get("@cat03", "")
        midpoint = RENT_CLASS_MIDPOINT.get(cat03)
        if midpoint is None:
            continue  # "0円" / "不詳" / "総数" / 未定義階級
        pref_code = _area_to_pref(area)
        if pref_code is None:
            continue
        try:
            count = float(str(v.get("$", "0")).replace(",", ""))
        except ValueError:
            continue
        if count <= 0:
            continue
        weighted_sum[pref_code] += midpoint * count
        total_count[pref_code] += count
        time_code = v.get("@time", "")
        if time_code and len(time_code) >= 4 and time_code[:4].isdigit():
            year_str = time_code[:4]
            iso = f"{year_str}-01-01"
            if measured_at is None or iso > measured_at:
                measured_at = iso

    for pref_code, wsum in weighted_sum.items():
        n = total_count[pref_code]
        if n <= 0:
            continue
        avg_rent = wsum / n
        yield {
            "indicator_id": "rent_index",
            "prefecture_code": pref_code,
            "value": avg_rent,
            "measured_at": measured_at,
        }


def _area_to_pref(area: str) -> str | None:
    """`01000` 等 → `01`(JIS X 0401). 全国/市区町村/不正コードは None."""
    if len(area) < 5 or not area[:5].isdigit():
        return None
    pref = area[:2]
    if pref == "00":
        return None  # 全国計
    # 下 3 桁が 000 でなければ市区町村レベル(本表は都道府県レベルで集計済みなのでスキップ)
    if area[2:5] != "000":
        return None
    if 1 <= int(pref) <= 47:
        return pref
    return None
