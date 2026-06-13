"""map_view 用データ取得ファサード.

DB 接続を試み、テーブルが空 or 接続不可なら `dummy.py` にフォールバックする.
ローンチ前の段階で「実データがあれば実データ、無ければダミー」のハイブリッド動作を実現.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Literal

import duckdb

from app.features.map_view.dummy import (
    PREDICTABLE_INDICATORS,
    PREF_CODES,
    dummy_value,
    dummy_values_for,
)
from app.shared.config import load_config
from app.shared.db import connect, initialize_schema
from app.shared.logger import get_logger

logger = get_logger(__name__)

Horizon = Literal["current", "3y", "5y", "10y"]
HORIZON_TO_YEARS: dict[Horizon, int] = {"3y": 3, "5y": 5, "10y": 10}

# AI モデル(ARIMA+Prophet)の R² が不十分(< 0.6)で no_prediction が出た場合の
# **簡易外挿フォールバック** に使う年率トレンド.
# データソース切替で履歴が短くなり ML 学習が破綻したケースの当面の救済策.
# 将来、月次バッチで履歴が蓄積されれば ML 予測に戻る.
_SIMPLE_FORECAST_RATES: dict[str, float] = {
    # 予測対象 4 指標(ARIMA/Prophet 想定だが履歴不足で外挿フォールバック)
    "price_index": 0.005,    # +0.5%/年(緩やかなインフレ前提)
    "land_price": 0.005,     # +0.5%/年
    "rent_index": 0.010,     # +1.0%/年
    "birth_count": -0.025,   # -2.5%/年(少子化トレンド)
    # 予測対象外 4 指標(シナリオベースのトレンド反映、過去傾向 + 地域特性)
    "air_quality": -0.010,   # -1.0%/年(規制強化 AQI 改善傾向)
    "disaster_risk": 0.005,  # +0.5%/年(気候変動で微増)
    "transport_access": 0.005,  # +0.5%/年(全国インフラ整備)
    "public_safety": -0.015,  # -1.5%/年(認知件数の全国減少傾向)
    # net_migration は率(‰)のため複利ではなく加算式で扱う(_net_migration_extrapolate)
}

# 三大都市圏(東京/神奈川/埼玉/千葉/大阪/愛知)
_BIG_THREE_METRO: frozenset[str] = frozenset({"13", "14", "11", "12", "27", "23"})
# 政令市圏・地方中核都市(札幌/仙台/京都/兵庫/広島/福岡 等)
_REGIONAL_HUBS: frozenset[str] = frozenset({"01", "04", "26", "28", "33", "34", "40", "43"})


def _pref_trend_modifier(indicator_id: str, pref_code: str) -> float:
    """県別の年率補正係数(1.0 = 標準).

    実際の傾向を反映:
        - 地価/賃料/物価: 三大都市圏は大きく上昇、地方は伸びが鈍い
        - 出生数: 都市圏は減少緩やか、地方は急減
        - 空気質: 都市圏は脱工業化で改善大、地方は黄砂等で改善鈍い
        - 災害リスク: 沿岸部・河川域(三大都市圏含む)で気候変動の影響大
        - 交通アクセス: 都市圏は新線・地下鉄延伸で改善、地方郡部は路線廃止で悪化
        - 治安(認知件数): 都市圏は犯罪減少幅大、地方は変化小
    """
    if indicator_id in ("land_price", "rent_index", "price_index"):
        if pref_code in _BIG_THREE_METRO:
            return 2.5
        if pref_code in _REGIONAL_HUBS:
            return 1.4
        return 0.4
    if indicator_id == "birth_count":
        if pref_code in _BIG_THREE_METRO:
            return 0.4
        if pref_code in _REGIONAL_HUBS:
            return 0.8
        return 1.6
    if indicator_id == "air_quality":
        if pref_code in _BIG_THREE_METRO:
            return 1.5
        if pref_code in _REGIONAL_HUBS:
            return 1.0
        return 0.5
    if indicator_id == "disaster_risk":
        if pref_code in _BIG_THREE_METRO:
            return 1.5
        if pref_code in _REGIONAL_HUBS:
            return 1.2
        return 1.0
    if indicator_id == "transport_access":
        if pref_code in _BIG_THREE_METRO:
            return 1.2
        if pref_code in _REGIONAL_HUBS:
            return 0.5
        return -1.0  # 地方郡部は路線廃止等で悪化(年率反転)
    if indicator_id == "public_safety":
        if pref_code in _BIG_THREE_METRO:
            return 1.5
        if pref_code in _REGIONAL_HUBS:
            return 1.0
        return 0.5
    return 1.0


def _net_migration_delta_per_year(pref_code: str) -> float:
    """net_migration(率‰)用の加算式 1 年あたり変化量.

    都市集中・地方流出のトレンドを反映:
        - 三大都市圏: +0.05‰/年(流入加速)
        - 地方中核: 0(横ばい)
        - 地方郡部: -0.10‰/年(流出加速)
    """
    if pref_code in _BIG_THREE_METRO:
        return 0.05
    if pref_code in _REGIONAL_HUBS:
        return 0.0
    return -0.10


def _simple_extrapolate(
    indicator_id: str,
    current_value: float,
    years: int,
    pref_code: str | None = None,
) -> float:
    """現在値 + 県別補正トレンド で簡易外挿.

    net_migration は率(‰)なので加算式、その他は複利.
    pref_code を渡すと県別補正が掛かり、偏差値(=相対順位)が時間で動く.
    """
    if indicator_id == "net_migration":
        delta = _net_migration_delta_per_year(pref_code) if pref_code else 0.0
        return current_value + delta * years

    base_rate = _SIMPLE_FORECAST_RATES.get(indicator_id, 0.0)
    modifier = _pref_trend_modifier(indicator_id, pref_code) if pref_code else 1.0
    rate = base_rate * modifier
    return current_value * ((1.0 + rate) ** years)


@dataclass(frozen=True, slots=True)
class DataAvailability:
    """データ取得元の表示用."""

    source: Literal["db", "dummy"]
    last_updated: datetime | None = None
    note: str | None = None


@dataclass(frozen=True, slots=True)
class ValueWithMeta:
    values: dict[str, float | None]
    availability: DataAvailability


@dataclass(frozen=True, slots=True)
class ModelInfo:
    indicator_id: str
    model_type: str | None
    trained_at: datetime | None
    r_squared: float | None
    mae: float | None
    evaluation_period: dict[str, str] | None
    parameters: dict | None  # type: ignore[type-arg]
    features_used: list[str] | None
    availability: DataAvailability


def _try_connect_readonly() -> duckdb.DuckDBPyConnection | None:
    """DB ファイルが存在すれば読み取り接続を返す。なければ None."""
    config = load_config()
    if not Path(config.db_path).exists():
        return None
    try:
        con = connect(protect_history=True)
        initialize_schema(con)
        return con
    except Exception:  # noqa: BLE001
        logger.exception("DB connect failed; falling back to dummy")
        return None


def _current_value_row_count(con: duckdb.DuckDBPyConnection) -> int:
    (n,) = con.execute("SELECT COUNT(*) FROM current_values").fetchone()
    return int(n)


def values_for(indicator_id: str, horizon: Horizon) -> ValueWithMeta:
    """指定指標・時点について 47 都道府県の {pref_code: value or None} を返す.

    取得先優先順位:
        1. current_values / predicted_values テーブル(DB)
        2. dummy_values_for(フォールバック)
    """
    con = _try_connect_readonly()
    if con is None:
        return ValueWithMeta(
            values=dummy_values_for(indicator_id, horizon),
            availability=DataAvailability(source="dummy", note="DB ファイル未生成。scripts/seed.py を実行してください"),
        )
    try:
        if horizon == "current":
            # 現在値 horizon は current_values を読む
            if _current_value_row_count(con) == 0:
                return ValueWithMeta(
                    values=dummy_values_for(indicator_id, horizon),
                    availability=DataAvailability(source="dummy", note="DB は初期化済みですが current_values が空です"),
                )
            rows = con.execute(
                """
                SELECT prefecture_code, value, updated_at
                FROM current_values
                WHERE indicator_id = $1
                """,
                [indicator_id],
            ).fetchall()
            values: dict[str, float | None] = dict.fromkeys(PREF_CODES)
            latest: datetime | None = None
            for code, value, updated_at in rows:
                values[code] = float(value) if value is not None else None
                if updated_at is not None and (latest is None or updated_at > latest):
                    latest = updated_at
            if not any(v is not None for v in values.values()):
                return ValueWithMeta(
                    values=dummy_values_for(indicator_id, horizon),
                    availability=DataAvailability(source="dummy", note=f"current_values に {indicator_id} のデータなし"),
                )
            return ValueWithMeta(values=values, availability=DataAvailability(source="db", last_updated=latest))

        # 未来予測 horizon
        if indicator_id not in PREDICTABLE_INDICATORS:
            # 予測対象外指標(空気/災害/交通/治安/人口流入)は、
            # 現在値 + 県別シナリオトレンドで外挿(_SIMPLE_FORECAST_RATES に登録された指標のみ).
            if _current_value_row_count(con) > 0:
                rows = con.execute(
                    """
                    SELECT prefecture_code, value, updated_at
                    FROM current_values
                    WHERE indicator_id = $1
                    """,
                    [indicator_id],
                ).fetchall()
                years_inherit = HORIZON_TO_YEARS[horizon]
                values_inherit: dict[str, float | None] = dict.fromkeys(PREF_CODES)
                latest_inherit: datetime | None = None
                use_extrapolation = (
                    indicator_id in _SIMPLE_FORECAST_RATES or indicator_id == "net_migration"
                )
                for code, value, updated_at in rows:
                    if value is None:
                        values_inherit[code] = None
                    elif use_extrapolation:
                        values_inherit[code] = _simple_extrapolate(
                            indicator_id, float(value), years_inherit, pref_code=code
                        )
                    else:
                        values_inherit[code] = float(value)
                    if updated_at is not None and (latest_inherit is None or updated_at > latest_inherit):
                        latest_inherit = updated_at
                if any(v is not None for v in values_inherit.values()):
                    note_msg = (
                        "予測対象外: 県別シナリオトレンドで外挿"
                        if use_extrapolation
                        else "予測対象外: 現在値を将来時点に継承"
                    )
                    return ValueWithMeta(
                        values=values_inherit,
                        availability=DataAvailability(
                            source="db",
                            last_updated=latest_inherit,
                            note=note_msg,
                        ),
                    )
            # current_values も空なら従来通り全 None
            return ValueWithMeta(
                values=dict.fromkeys(PREF_CODES),
                availability=DataAvailability(source="db", note="この指標は予測対象外"),
            )

        years = HORIZON_TO_YEARS[horizon]
        rows = con.execute(
            """
            SELECT prefecture_code, value, quality_status, predicted_at
            FROM predicted_values
            WHERE indicator_id = $1 AND horizon_years = $2
            """,
            [indicator_id, years],
        ).fetchall()
        # predicted_values が完全に空でも、予測対象指標は現在値 × 県別年率で補完できる
        # サンプル DB 等(run_batch.py 未実行)の初期状態でも UI に値を出すための救済策
        result: dict[str, float | None] = dict.fromkeys(PREF_CODES)
        latest = None
        no_prediction_codes: list[str] = []
        filled_codes: set[str] = set()
        for code, value, quality, predicted_at in rows:
            if quality == "no_prediction":
                result[code] = None
                no_prediction_codes.append(code)
            elif value is not None:
                result[code] = float(value)
                filled_codes.add(code)
            if predicted_at is not None and (latest is None or predicted_at > latest):
                latest = predicted_at

        # フォールバック対象 = (a) no_prediction セル + (b) predicted_values 行なしセル
        fallback_codes = [
            code for code in PREF_CODES
            if code not in filled_codes and result[code] is None
        ]
        note = None
        if fallback_codes and indicator_id in _SIMPLE_FORECAST_RATES:
            current_rows = con.execute(
                """
                SELECT prefecture_code, value
                FROM current_values
                WHERE indicator_id = $1 AND prefecture_code = ANY($2)
                """,
                [indicator_id, fallback_codes],
            ).fetchall()
            current_lookup = {c: float(v) for c, v in current_rows if v is not None}
            filled = 0
            for code in fallback_codes:
                if code in current_lookup:
                    result[code] = _simple_extrapolate(
                        indicator_id, current_lookup[code], years, pref_code=code
                    )
                    filled += 1
            if filled > 0:
                note = (
                    f"現在値 × 県別簡易年率で {filled} 件を補完"
                    "(predicted_values 不足を救済、三大都市圏/地方中核/地方郡部で別)"
                )

        # 何も埋まらなかった場合のみ dummy にフォールバック(完全な無データ)
        if all(v is None for v in result.values()):
            return ValueWithMeta(
                values=dummy_values_for(indicator_id, horizon),
                availability=DataAvailability(source="dummy", note=f"predicted_values + current_values 共に {indicator_id} のデータなし"),
            )

        return ValueWithMeta(
            values=result,
            availability=DataAvailability(source="db", last_updated=latest, note=note),
        )
    finally:
        con.close()


def value_for(indicator_id: str, prefecture_code: str, horizon: Horizon) -> float | None:
    """特定セルの値."""
    pack = values_for(indicator_id, horizon)
    return pack.values.get(prefecture_code)


def values_for_all_indicators(
    indicator_ids: tuple[str, ...],
    horizon: Horizon,
) -> dict[str, dict[str, float | None]]:
    """指定 horizon について **1 DB 接続で** 複数指標 × 47 都道府県を一括取得.

    compute_ranking のパフォーマンス改善用. 個別 values_for() を 9 回呼ぶと
    9 回 connect + initialize_schema が走るが、本関数は 1 回で済ませる.

    Args:
        indicator_ids: 取得対象の指標 ID タプル.
        horizon: 'current' / '3y' / '5y' / '10y'.

    Returns:
        {indicator_id: {pref_code: value or None}}.
    """
    # DB 接続不可ならフォールバック(個別ダミー)
    con = _try_connect_readonly()
    if con is None:
        return {ind: dummy_values_for(ind, horizon) for ind in indicator_ids}

    try:
        # 現在値テーブルが空か事前チェック
        if _current_value_row_count(con) == 0:
            return {ind: dummy_values_for(ind, horizon) for ind in indicator_ids}

        result: dict[str, dict[str, float | None]] = {
            ind: dict.fromkeys(PREF_CODES) for ind in indicator_ids
        }

        if horizon == "current":
            # 全 indicators の current_values をまとめて取得
            rows = con.execute(
                """
                SELECT indicator_id, prefecture_code, value
                FROM current_values
                WHERE indicator_id = ANY($1)
                """,
                [list(indicator_ids)],
            ).fetchall()
            for ind, code, value in rows:
                if ind in result and code in result[ind]:
                    result[ind][code] = float(value) if value is not None else None
            return result

        # 未来 horizon: 予測可能指標は predicted_values から、それ以外は current_values × シナリオ外挿
        years = HORIZON_TO_YEARS[horizon]
        predictable_ids = [i for i in indicator_ids if i in PREDICTABLE_INDICATORS]
        non_predictable_ids = [i for i in indicator_ids if i not in PREDICTABLE_INDICATORS]

        # 予測対象外: 現在値 + 県別シナリオトレンド(空気/災害/交通/治安/人口流入)
        if non_predictable_ids:
            rows = con.execute(
                """
                SELECT indicator_id, prefecture_code, value
                FROM current_values
                WHERE indicator_id = ANY($1)
                """,
                [non_predictable_ids],
            ).fetchall()
            for ind, code, value in rows:
                if ind not in result or code not in result[ind]:
                    continue
                if value is None:
                    continue
                # _SIMPLE_FORECAST_RATES or net_migration の場合は外挿、それ以外は継承
                if ind in _SIMPLE_FORECAST_RATES or ind == "net_migration":
                    result[ind][code] = _simple_extrapolate(
                        ind, float(value), years, pref_code=code
                    )
                else:
                    result[ind][code] = float(value)

        # 予測対象: predicted_values から取得、不足分は簡易外挿で補完
        # フォールバック対象:
        #   (a) quality_status='no_prediction' のセル
        #   (b) predicted_values にそもそも行が無いセル(サンプル DB 等の初期状態)
        if predictable_ids:
            rows = con.execute(
                """
                SELECT indicator_id, prefecture_code, value, quality_status
                FROM predicted_values
                WHERE indicator_id = ANY($1) AND horizon_years = $2
                """,
                [predictable_ids, years],
            ).fetchall()
            # predicted_values からセットしたセルを記録
            filled_by_ind: dict[str, set[str]] = {ind: set() for ind in predictable_ids}
            for ind, code, value, quality in rows:
                if ind not in result or code not in result[ind]:
                    continue
                if quality == "no_prediction":
                    # (a) フォールバック対象 — filled_by_ind には入れない
                    continue
                if value is not None:
                    result[ind][code] = float(value)
                    filled_by_ind[ind].add(code)

            # (a) + (b) 両方をまとめてフォールバック対象にする
            needs_fallback: dict[str, list[str]] = {}
            for ind in predictable_ids:
                if ind not in _SIMPLE_FORECAST_RATES:
                    continue
                missing_codes = [
                    code for code in PREF_CODES
                    if code not in filled_by_ind[ind] and result[ind].get(code) is None
                ]
                if missing_codes:
                    needs_fallback[ind] = missing_codes

            if needs_fallback:
                current_rows = con.execute(
                    """
                    SELECT indicator_id, prefecture_code, value
                    FROM current_values
                    WHERE indicator_id = ANY($1)
                    """,
                    [list(needs_fallback.keys())],
                ).fetchall()
                current_lookup: dict[str, dict[str, float]] = {}
                for ind, code, value in current_rows:
                    if value is None:
                        continue
                    current_lookup.setdefault(ind, {})[code] = float(value)
                for ind, codes in needs_fallback.items():
                    for code in codes:
                        cv = current_lookup.get(ind, {}).get(code)
                        if cv is not None:
                            result[ind][code] = _simple_extrapolate(
                                ind, cv, years, pref_code=code
                            )

        return result
    finally:
        con.close()


def prefecture_full_table(prefecture_code: str) -> dict[str, dict[Horizon, float | None]]:
    """1 都道府県分の {indicator_id: {horizon: value}} を返す.

    予測対象外 × 未来 horizon は None.
    DB 空ならダミー値を全埋め.

    パフォーマンス: 7 指標 × 4 時点 = 28 セルを **2 SQL クエリ**(current + predicted)
    で取得して埋める. 以前は 28 個別 connect を行っていたが、単一接続に最適化.
    """
    horizons: tuple[Horizon, ...] = ("current", "3y", "5y", "10y")
    indicators = (
        "price_index",
        "land_price",
        "rent_index",
        "birth_count",
        "air_quality",
        "disaster_risk",
        "transport_access",
    )

    # 初期化(全 None)
    table: dict[str, dict[Horizon, float | None]] = {ind: dict.fromkeys(horizons) for ind in indicators}

    con = _try_connect_readonly()
    db_has_current = False
    db_has_predicted_for: set[str] = set()
    if con is not None:
        try:
            # 現在値: 該当都道府県の全指標
            rows = con.execute(
                """
                SELECT indicator_id, value
                FROM current_values
                WHERE prefecture_code = $1
                """,
                [prefecture_code],
            ).fetchall()
            for ind, value in rows:
                if ind in table and value is not None:
                    table[ind]["current"] = float(value)
                    db_has_current = True

            # 予測値: 主要指標のみ
            rows = con.execute(
                """
                SELECT indicator_id, horizon_years, value, quality_status
                FROM predicted_values
                WHERE prefecture_code = $1
                """,
                [prefecture_code],
            ).fetchall()
            for ind, hy, value, quality in rows:
                if ind not in table:
                    continue
                horizon_key: Horizon = f"{hy}y"  # type: ignore[assignment]
                if horizon_key in horizons:
                    if quality == "no_prediction":
                        table[ind][horizon_key] = None
                    elif value is not None:
                        table[ind][horizon_key] = float(value)
                    db_has_predicted_for.add(ind)
        finally:
            con.close()

    # 1. まず current を埋める(dummy 含めて確定)
    for ind in indicators:
        if table[ind]["current"] is None and not db_has_current:
            table[ind]["current"] = dummy_value(ind, prefecture_code, "current")

    # 2. 次に未来 horizon を埋める
    #   - 予測対象外指標 × 未来 → 現在値を継承
    #   - 主要4指標で AI 予測が no_prediction → 現在値 × 簡易年率で外挿
    #   - DB に予測なし → dummy
    horizon_year_map: dict[Horizon, int] = {"3y": 3, "5y": 5, "10y": 10}
    for ind in indicators:
        is_predictable = ind in PREDICTABLE_INDICATORS
        current_val = table[ind].get("current")  # 上記で埋め済み
        for h in horizons:
            if h == "current" or table[ind][h] is not None:
                continue
            years = horizon_year_map.get(h)  # type: ignore[arg-type]
            if not is_predictable:
                # 予測対象外も外挿対象指標(空気/災害/交通/治安/人口流入)はトレンドで動かす
                if current_val is None:
                    continue
                if (
                    ind in _SIMPLE_FORECAST_RATES or ind == "net_migration"
                ) and years is not None:
                    table[ind][h] = _simple_extrapolate(
                        ind, current_val, years, pref_code=prefecture_code
                    )
                else:
                    table[ind][h] = current_val
            elif ind in _SIMPLE_FORECAST_RATES and current_val is not None and years is not None:
                table[ind][h] = _simple_extrapolate(
                    ind, current_val, years, pref_code=prefecture_code
                )
            elif ind not in db_has_predicted_for:
                table[ind][h] = dummy_value(ind, prefecture_code, h)
    return table


def latest_model_for(indicator_id: str) -> ModelInfo:
    """最新の prediction_model と model_evaluation を返す.

    DB 未準備/該当指標未学習なら dummy 情報を返す.
    """
    con = _try_connect_readonly()
    if con is None or indicator_id not in PREDICTABLE_INDICATORS:
        return _dummy_model_info(indicator_id)
    try:
        row = con.execute(
            """
            SELECT id, model_type, trained_at, parameters, features_used, training_data_range
            FROM prediction_models
            WHERE indicator_id = $1
            ORDER BY trained_at DESC
            LIMIT 1
            """,
            [indicator_id],
        ).fetchone()
        if row is None:
            return _dummy_model_info(indicator_id)
        model_id, model_type, trained_at, params, features, _data_range = row

        ev = con.execute(
            """
            SELECT r_squared, mae, evaluation_period
            FROM model_evaluations
            WHERE model_id = $1
            ORDER BY evaluated_at DESC
            LIMIT 1
            """,
            [model_id],
        ).fetchone()
        if ev is None:
            r2, mae, period = None, None, None
        else:
            r2, mae, period_raw = ev
            period = _parse_json(period_raw)
        return ModelInfo(
            indicator_id=indicator_id,
            model_type=str(model_type) if model_type else None,
            trained_at=trained_at,
            r_squared=float(r2) if r2 is not None else None,
            mae=float(mae) if mae is not None else None,
            evaluation_period=period,
            parameters=_parse_json(params),
            features_used=_parse_json(features),
            availability=DataAvailability(source="db", last_updated=trained_at),
        )
    finally:
        con.close()


def _parse_json(raw):  # type: ignore[no-untyped-def]
    """DuckDB の JSON 列値を Python に."""
    if raw is None:
        return None
    if isinstance(raw, (dict, list)):
        return raw
    if isinstance(raw, str):
        import json

        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return None
    return None


def _dummy_model_info(indicator_id: str) -> ModelInfo:
    return ModelInfo(
        indicator_id=indicator_id,
        model_type="arima(2,1,2) — ダミー",
        trained_at=None,
        r_squared=0.72,
        mae=1.4,
        evaluation_period={"from": "2024-01", "to": "2026-04"},
        parameters={"order": [2, 1, 2]},
        features_used=["lag_1", "lag_3", "lag_6", "lag_12"],
        availability=DataAvailability(source="dummy", note="DB に学習済モデルがないためダミー表示"),
    )


__all__ = [
    "DataAvailability",
    "ModelInfo",
    "ValueWithMeta",
    "latest_model_for",
    "prefecture_full_table",
    "value_for",
    "values_for",
]


# 型チェッカー用のダミー import 取り扱い
_ = (date,)  # date import 保持(prefecture_full_table 拡張時用)
