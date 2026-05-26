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
    "price_index": 0.005,   # +0.5%/年(緩やかなインフレ前提)
    "land_price": 0.005,    # +0.5%/年
    "rent_index": 0.010,    # +1.0%/年
    "birth_count": -0.025,  # -2.5%/年(少子化トレンド)
}


def _simple_extrapolate(indicator_id: str, current_value: float, years: int) -> float:
    """現在値 × (1 + 年率)^years で簡易外挿."""
    rate = _SIMPLE_FORECAST_RATES.get(indicator_id, 0.0)
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
            values: dict[str, float | None] = {code: None for code in PREF_CODES}
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
            # 予測対象外指標(空気質/災害/交通)は将来も「現状と同じ」と仮定し、
            # 現在値をそのまま返す(ランキング・比較で None になる UX 問題回避).
            # quality_status 上は推測値だが、データ源の性質(地形/施設等で年単位の急変が少ない)から妥当.
            if _current_value_row_count(con) > 0:
                rows = con.execute(
                    """
                    SELECT prefecture_code, value, updated_at
                    FROM current_values
                    WHERE indicator_id = $1
                    """,
                    [indicator_id],
                ).fetchall()
                values_inherit: dict[str, float | None] = {code: None for code in PREF_CODES}
                latest_inherit: datetime | None = None
                for code, value, updated_at in rows:
                    values_inherit[code] = float(value) if value is not None else None
                    if updated_at is not None and (latest_inherit is None or updated_at > latest_inherit):
                        latest_inherit = updated_at
                if any(v is not None for v in values_inherit.values()):
                    return ValueWithMeta(
                        values=values_inherit,
                        availability=DataAvailability(
                            source="db",
                            last_updated=latest_inherit,
                            note="予測対象外: 現在値を将来時点に継承",
                        ),
                    )
            # current_values も空なら従来通り全 None
            return ValueWithMeta(
                values={code: None for code in PREF_CODES},
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
        if not rows:
            return ValueWithMeta(
                values=dummy_values_for(indicator_id, horizon),
                availability=DataAvailability(source="dummy", note=f"predicted_values に {indicator_id}/{horizon} のデータなし"),
            )

        result: dict[str, float | None] = {code: None for code in PREF_CODES}
        latest = None
        no_prediction_codes: list[str] = []
        for code, value, quality, predicted_at in rows:
            if quality == "no_prediction":
                result[code] = None
                no_prediction_codes.append(code)
            else:
                result[code] = float(value) if value is not None else None
            if predicted_at is not None and (latest is None or predicted_at > latest):
                latest = predicted_at

        # ML モデルが no_prediction を出した予測値を、現在値 × 仮定年率 で補完
        # (履歴データ不足で ARIMA/Prophet が機能しない場合の救済策)
        note = None
        if no_prediction_codes and indicator_id in _SIMPLE_FORECAST_RATES:
            current_rows = con.execute(
                """
                SELECT prefecture_code, value
                FROM current_values
                WHERE indicator_id = $1 AND prefecture_code = ANY($2)
                """,
                [indicator_id, no_prediction_codes],
            ).fetchall()
            current_lookup = {c: float(v) for c, v in current_rows if v is not None}
            filled = 0
            for code in no_prediction_codes:
                if code in current_lookup:
                    result[code] = _simple_extrapolate(indicator_id, current_lookup[code], years)
                    filled += 1
            if filled > 0:
                note = f"AI予測精度不足 {filled} 件を現在値 × 簡易年率(+/-1〜2.5%)で補完"

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
    table: dict[str, dict[Horizon, float | None]] = {ind: {h: None for h in horizons} for ind in indicators}

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
                if current_val is not None:
                    table[ind][h] = current_val
            elif ind in _SIMPLE_FORECAST_RATES and current_val is not None and years is not None:
                table[ind][h] = _simple_extrapolate(ind, current_val, years)
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
