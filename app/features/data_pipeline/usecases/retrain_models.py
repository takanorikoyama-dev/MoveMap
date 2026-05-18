"""SF-015 RetrainModels — 主要4指標の予測モデル再学習.

参照: outputs/06_system_design/04_データ設計.md (prediction_models)
持ち越し: TECH-04 ARIMA vs Prophet 評価、DE-02 指標別頻度

設計: 1 指標について 47 都道府県分の時系列を個別学習.
prediction_models には「指標ごとに 1 行」を作り、parameters JSON にメタを格納.
fitted モデル本体は in-memory(`PredictionState.fitted`)で保持し、後続 Usecase に引き継ぐ.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

import duckdb

from app.features.data_pipeline.models import arima, prophet_model
from app.shared.logger import get_logger

logger = get_logger(__name__)

PREDICTABLE_INDICATORS: tuple[str, ...] = ("price_index", "land_price", "rent_index", "birth_count")
DEFAULT_MODEL_TYPE = "arima"  # Phase 5 で確定したデフォルト. Prophet 比較は Phase 8 で.


@dataclass
class PredictionState:
    """RetrainModels → EvaluateModels → GeneratePredictions → ApplyFallback 間の引き継ぎ.

    DB には保存しない一時状態(fitted model 本体は pickle 不向きのため).
    """

    # indicator_id → prediction_models.id
    model_ids: dict[str, int] = field(default_factory=dict)
    # indicator_id → {prefecture_code: fitted_state}(arima.train_arima の戻り値)
    fitted: dict[str, dict[str, dict[str, Any]]] = field(default_factory=dict)


def retrain_models(con: duckdb.DuckDBPyConnection, model_type: str = DEFAULT_MODEL_TYPE) -> PredictionState:
    """主要4指標について、47 都道府県分の時系列モデルを学習する.

    Args:
        con: DuckDB 接続.
        model_type: 'arima' または 'prophet'.

    Returns:
        PredictionState(下流 Usecase に渡す).
    """
    if model_type not in ("arima", "prophet"):
        raise ValueError(f"unsupported model_type: {model_type}")

    state = PredictionState()
    train_fn = arima.train_arima if model_type == "arima" else prophet_model.train_prophet
    insufficient_exc = arima.InsufficientHistoryError if model_type == "arima" else prophet_model.InsufficientHistoryError

    for indicator_id in PREDICTABLE_INDICATORS:
        per_pref: dict[str, dict[str, Any]] = {}
        prefectures = [row[0] for row in con.execute("SELECT code FROM prefectures ORDER BY code").fetchall()]

        ranges: dict[str, dict[str, str]] = {}
        skipped = 0
        for pref in prefectures:
            history_rows = con.execute(
                """
                SELECT measured_at, value
                FROM historical_values
                WHERE prefecture_code = $1 AND indicator_id = $2
                ORDER BY measured_at
                """,
                [pref, indicator_id],
            ).fetchall()
            history: list[tuple[str, float]] = [(row[0].isoformat() if hasattr(row[0], "isoformat") else str(row[0]), float(row[1])) for row in history_rows]

            try:
                per_pref[pref] = train_fn(history)
                if history:
                    ranges[pref] = {"from": history[0][0], "to": history[-1][0]}
            except insufficient_exc:
                skipped += 1
                logger.warning(f"skip {indicator_id}/{pref}: history too short ({len(history)})")

        if not per_pref:
            logger.warning(f"no usable history for {indicator_id}; model not registered")
            continue

        parameters = {
            "trained_prefectures": list(per_pref.keys()),
            "skipped_prefectures": skipped,
            "model_type": model_type,
        }
        features_used = ["lag_1", "lag_3", "lag_6", "lag_12"]
        # 訓練範囲は全都道府県のうち最も狭い範囲を採用
        training_data_range = _merge_ranges(ranges)

        result = con.execute(
            """
            INSERT INTO prediction_models
                (indicator_id, model_type, parameters, features_used, training_data_range)
            VALUES ($1, $2, $3, $4, $5)
            RETURNING id
            """,
            [indicator_id, model_type, json.dumps(parameters), json.dumps(features_used), json.dumps(training_data_range)],
        ).fetchone()
        if result is None:
            logger.error(f"failed to insert prediction_models for {indicator_id}")
            continue
        model_id = int(result[0])
        state.model_ids[indicator_id] = model_id
        state.fitted[indicator_id] = per_pref
        logger.info(f"trained {indicator_id}: model_id={model_id}, prefs={len(per_pref)}, skipped={skipped}")

    return state


def _merge_ranges(ranges: dict[str, dict[str, str]]) -> dict[str, str]:
    """全都道府県の訓練範囲のうち、共通区間(最大 from, 最小 to)を返す."""
    if not ranges:
        return {"from": "", "to": ""}
    froms = [r["from"] for r in ranges.values() if r.get("from")]
    tos = [r["to"] for r in ranges.values() if r.get("to")]
    return {"from": max(froms) if froms else "", "to": min(tos) if tos else ""}
