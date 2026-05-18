"""SF-016 EvaluateModels — R²/MAE 評価.

参照: outputs/06_system_design/04_データ設計.md (model_evaluations)
持ち越し: OPS-02 評価期間の確定(現状: 直近 20% をホールドアウト).

R² / MAE は「47 都道府県の予測残差を集約した結果」として 1 モデル(= 1 指標)あたり 1 件記録する.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from typing import Any

import duckdb

from app.features.data_pipeline.models import arima
from app.features.data_pipeline.usecases.retrain_models import PredictionState
from app.shared.logger import get_logger

logger = get_logger(__name__)

HOLDOUT_RATIO = 0.2  # 直近 20% を評価に使う(OPS-02 で再検討)


@dataclass(frozen=True, slots=True)
class EvaluationResult:
    indicator_id: str
    model_id: int
    r_squared: float
    mae: float
    n_samples: int


def evaluate_models(con: duckdb.DuckDBPyConnection, state: PredictionState) -> dict[str, EvaluationResult]:
    """各モデル(指標)について R²/MAE を計算し model_evaluations へ保存する.

    Args:
        con: DuckDB 接続.
        state: RetrainModels の戻り値.

    Returns:
        {indicator_id: EvaluationResult}.
    """
    results: dict[str, EvaluationResult] = {}

    for indicator_id, model_id in state.model_ids.items():
        per_pref = state.fitted.get(indicator_id, {})
        residuals: list[float] = []
        observed: list[float] = []
        predicted: list[float] = []
        period_from: str = ""
        period_to: str = ""

        for pref, _model in per_pref.items():
            history_rows = con.execute(
                """
                SELECT measured_at, value FROM historical_values
                WHERE prefecture_code = $1 AND indicator_id = $2
                ORDER BY measured_at
                """,
                [pref, indicator_id],
            ).fetchall()
            if len(history_rows) < arima.MIN_OBSERVATIONS:
                continue
            n_total = len(history_rows)
            split = max(1, int(n_total * (1 - HOLDOUT_RATIO)))
            train = history_rows[:split]
            holdout = history_rows[split:]

            history: list[tuple[str, float]] = [(_iso(r[0]), float(r[1])) for r in train]
            try:
                fit = arima.train_arima(history)
            except arima.InsufficientHistoryError:
                continue

            # ホールドアウト各点について 1 ステップ予測の代わりに、終端予測を使う簡易評価
            last_index = len(holdout) - 1
            if last_index < 0:
                continue
            steps_per_year = 12
            horizon = max(1, math.ceil((last_index + 1) / steps_per_year))
            point, _, _ = arima.forecast(fit, horizon_years=horizon, points_per_year=steps_per_year)

            observed.append(float(holdout[last_index][1]))
            predicted.append(point)
            residuals.append(observed[-1] - point)

            if not period_from:
                period_from = _iso(holdout[0][0])
            period_to = _iso(holdout[last_index][0])

        if not residuals:
            logger.warning(f"no evaluation samples for {indicator_id}; skip model_evaluations row")
            continue

        r2 = _r_squared(observed, predicted)
        mae = sum(abs(r) for r in residuals) / len(residuals)

        con.execute(
            """
            INSERT INTO model_evaluations (model_id, r_squared, mae, evaluation_period)
            VALUES ($1, $2, $3, $4)
            """,
            [model_id, r2, mae, json.dumps({"from": period_from, "to": period_to})],
        )
        results[indicator_id] = EvaluationResult(
            indicator_id=indicator_id,
            model_id=model_id,
            r_squared=r2,
            mae=mae,
            n_samples=len(residuals),
        )
        logger.info(f"eval {indicator_id}: r2={r2:.3f} mae={mae:.3f} n={len(residuals)}")

    return results


def _r_squared(observed: list[float], predicted: list[float]) -> float:
    if not observed or len(observed) != len(predicted):
        return 0.0
    mean = sum(observed) / len(observed)
    ss_tot = sum((y - mean) ** 2 for y in observed)
    ss_res = sum((y - p) ** 2 for y, p in zip(observed, predicted, strict=True))
    if ss_tot == 0:
        return 0.0 if ss_res > 0 else 1.0
    return 1.0 - ss_res / ss_tot


def _iso(value: Any) -> str:
    if hasattr(value, "isoformat"):
        return value.isoformat()  # type: ignore[no-any-return]
    return str(value)
