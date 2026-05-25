"""API-EXT-01 e-Stat アダプタ(物価指数・出生数).

e-Stat API v3.0 の `getStatsData` で都道府県別データを取得する.

参照: https://www.e-stat.go.jp/api/api-info/e-stat-manual3-0
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from app.features.data_pipeline.sources._base import DataSourceAdapter
from app.shared.config import load_config
from app.shared.http_client import (
    HttpRetryExhausted,
    HttpSchemaError,
    get_json,
    head_last_modified,
)
from app.shared.logger import get_logger

logger = get_logger(__name__)

E_STAT_BASE_URL = "https://api.e-stat.go.jp/rest/3.0/app/json"
GET_STATS_DATA = f"{E_STAT_BASE_URL}/getStatsData"

# 内部 indicator_id ごとに必要なリクエストパラメータ(statsDataId + 絞り込み軸).
#
# price_index: 小売物価統計調査(構造編) 消費者物価地域差指数 / 0003441258 + cdCat01=00010(総合).
#   全国 = 100 を基準に地域間の **物価水準そのもの** を示す指数(東京は約 102、沖縄は約 99 など).
#   2026-05-26 までは CPI(0003143513、2020 年比の変動率)を使っていたが、ユーザーの
#   「東京は物価が高いはず」直感と乖離する数値が出るため切り替え.
# birth_count: 人口動態統計 確定数 保管統計表 都道府県別 出生(年次).
# rent_index : mlit_rent_index.py で住宅・土地統計調査の家賃階級加重平均.
INDICATOR_TO_STATS_PARAMS: dict[str, dict[str, str]] = {
    "price_index": {"statsDataId": "0003441258", "cdCat01": "00010"},
    "birth_count": {"statsDataId": "0003412062"},
}


class EStatAdapter(DataSourceAdapter):
    """e-Stat API クライアント.

    認証: ESTAT_APP_ID(環境変数)を `appId` クエリパラメータとして送信.
    """

    source_id = "estat"

    def __init__(self, app_id: str | None = None) -> None:
        config = load_config()
        self.app_id = app_id if app_id is not None else config.estat_app_id

    def fetch(self) -> Iterator[dict[str, Any]]:
        """物価指数・出生数を取得し、indicator_id ごとに正規化前レコードを yield する.

        Yields:
            {"indicator_id": ..., "prefecture_code": ..., "value": ..., "measured_at": ...}.

        Raises:
            RuntimeError: app_id 未設定.
            HttpRetryExhausted: API 失敗(C-01 を上流で処理).
        """
        if not self.app_id:
            raise RuntimeError("ESTAT_APP_ID が未設定。.env か Secrets で渡してください")

        for indicator_id, extra in INDICATOR_TO_STATS_PARAMS.items():
            stats_data_id = extra["statsDataId"]
            params: dict[str, Any] = {
                "appId": self.app_id,
                "statsDataId": stats_data_id,
                "metaGetFlg": "Y",
                "cntGetFlg": "N",
                "explanationGetFlg": "N",
                "annotationGetFlg": "N",
            }
            # statsDataId 以外のキー(cdCat01 等)はそのままリクエストに渡す
            for k, v in extra.items():
                if k != "statsDataId":
                    params[k] = v
            logger.info(f"e-Stat fetch: indicator={indicator_id} params={ {k: v for k, v in extra.items()} }")
            try:
                payload = get_json(GET_STATS_DATA, params=params)
            except HttpRetryExhausted:
                logger.exception(f"e-Stat fetch failed (retry exhausted): {indicator_id}")
                continue

            yield from self._parse_stats_data(indicator_id, payload)

    def last_updated(self) -> str | None:
        """HEAD では確実な情報が取れないため `None` を返す.

        差分判定は `getStatsList` を別途呼ぶことで実装可能だが、Phase 7 続セッションで対応.
        """
        return head_last_modified(E_STAT_BASE_URL)

    @staticmethod
    def _parse_stats_data(indicator_id: str, payload: dict[str, Any]) -> Iterator[dict[str, Any]]:
        """e-Stat API の getStatsData レスポンスから (都道府県, 値) を抽出.

        e-Stat の JSON 構造:
            GET_STATS_DATA.STATISTICAL_DATA.DATA_INF.VALUE: [{"@cat01": ..., "@area": "01000", "$": "100.0"}, ...]

        都道府県ごとに `@time` が最も新しいレコードだけを採用する.
        e-Stat は同一都道府県で過去全月/全年分を返すため、後段の current_values
        upsert で値が順序依存にならないようにここでフィルタする.

        Raises:
            HttpSchemaError: 期待構造と異なる.
        """
        try:
            root = payload["GET_STATS_DATA"]["STATISTICAL_DATA"]
            data_inf = root["DATA_INF"]
            values = data_inf["VALUE"]
            if not isinstance(values, list):
                values = [values]
        except (KeyError, TypeError) as exc:
            raise HttpSchemaError(f"e-Stat response shape unexpected for {indicator_id}") from exc

        # pref_code → (time_code, record) で最新だけ保持
        latest: dict[str, tuple[str, dict[str, Any]]] = {}
        for v in values:
            area_code = v.get("@area")
            value_str = v.get("$")
            time_code = v.get("@time") or ""

            if not area_code or value_str is None:
                continue

            pref_code = _extract_prefecture_code(area_code)
            if pref_code is None:
                continue

            try:
                value = float(value_str)
            except ValueError:
                continue

            record = {
                "indicator_id": indicator_id,
                "prefecture_code": pref_code,
                "value": value,
                "measured_at": _time_code_to_iso(time_code) if time_code else None,
            }

            existing = latest.get(pref_code)
            if existing is None or time_code > existing[0]:
                latest[pref_code] = (time_code, record)

        for _, record in latest.values():
            yield record


def _extract_prefecture_code(area_code: str) -> str | None:
    """e-Stat の area_code から JIS X 0401 の 2 桁都道府県コードを取り出す.

    e-Stat の area_code は統計表ごとに粒度が異なる:
        - "01000" (都道府県レベル: 下 3 桁 = '000')
        - "13A01" (県庁所在地ベース、消費者物価指数等)
        - "01100" (市町村レベル: 都道府県内詳細)
        - "00000" (全国計)

    本関数は **先頭 2 桁が 01〜47 ならその都道府県のデータとして採用** する.
    同一県内で複数の area_code が返る場合、upsert で最後値が残る挙動を期待する.

    Examples:
        "01000" → "01" (北海道、県レベル)
        "13A01" → "13" (東京都・県庁所在地ベース)
        "01100" → "01" (北海道・市町村レベルもその県の値として採用)
        "00000" → None (全国計は除外)
        "ABCDE" → None (英字始まり)
    """
    if len(area_code) < 2:
        return None
    pref_part = area_code[:2]
    if not pref_part.isdigit():
        return None
    if pref_part == "00":
        return None  # 全国計
    if 1 <= int(pref_part) <= 47:
        return pref_part
    return None


def _time_code_to_iso(time_code: str) -> str | None:
    """e-Stat の time_code を ISO 日付に変換.

    Examples:
        "2024000000" → "2024-01-01" (年次データ)
        "2024010000" → "2024-01-01" (月次データ 1月)
        "2024120000" → "2024-12-01" (月次データ 12月)
    """
    if len(time_code) < 6 or not time_code.isdigit():
        return None
    year = time_code[:4]
    month = time_code[4:6]
    if month == "00":
        month = "01"
    if not (1 <= int(month) <= 12):
        return None
    return f"{year}-{month}-01"
