"""SF-017 GeneratePredictions — 47×4×3 予測値生成.

参照: outputs/06_system_design/04_データ設計.md (predicted_values)
不変条件:
    INV-DATA-003: PK (prefecture_code, indicator_id, horizon_years) 一意.
    INV-DATA-004/005: is_predictable=true の Indicator のみ.
    INV-DATA-006: horizon_years ∈ {3,5,10}.
"""

from __future__ import annotations

from typing import Literal

import duckdb

from app.features.data_pipeline.models import arima
from app.features.data_pipeline.usecases.retrain_models import PredictionState
from app.shared.logger import get_logger

logger = get_logger(__name__)

HORIZONS: tuple[Literal[3, 5, 10], ...] = (3, 5, 10)


def generate_predictions(con: duckdb.DuckDBPyConnection, state: PredictionState) -> int:
    """学習済みモデルから 47 都道府県 × 4 指標 × 3 時点 の予測値を upsert する.

    quality_status='good' で挿入する.
    R²<0.6 の指標は後段 ApplyFallback で no_prediction に変更される.

    Args:
        con: DuckDB 接続.
        state: RetrainModels の戻り値.

    Returns:
        upsert 件数.
    """
    count = 0
    for indicator_id, model_id in state.model_ids.items():
        per_pref = state.fitted.get(indicator_id, {})
        for pref_code, fit in per_pref.items():
            for horizon in HORIZONS:
                point, lower, upper = arima.forecast(fit, horizon_years=horizon)
                con.execute(
                    """
                    INSERT INTO predicted_values
                        (prefecture_code, indicator_id, horizon_years, value, ci_lower, ci_upper,
                         quality_status, model_id)
                    VALUES ($1, $2, $3, $4, $5, $6, 'good', $7)
                    ON CONFLICT (prefecture_code, indicator_id, horizon_years) DO UPDATE SET
                        value = excluded.value,
                        ci_lower = excluded.ci_lower,
                        ci_upper = excluded.ci_upper,
                        quality_status = 'good',
                        model_id = excluded.model_id,
                        predicted_at = now()
                    """,
                    [pref_code, indicator_id, horizon, point, lower, upper, model_id],
                )
                count += 1
    logger.info(f"generate_predictions: {count} rows upserted")
    return count
