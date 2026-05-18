"""SF-018 ApplyFallback — R²<0.6 の指標を no_prediction に.

参照: outputs/06_system_design/03_状態遷移.md (PredictedValue.quality_status)
不変条件:
    INV-BIZ-003: R²<0.6 から生成された PredictedValue は quality_status='no_prediction'.
    R1.4 品質閾値: R² ≥ 0.6.
"""

from __future__ import annotations

from collections.abc import Mapping

import duckdb

from app.features.data_pipeline.usecases.evaluate_models import EvaluationResult
from app.shared.logger import get_logger

logger = get_logger(__name__)

R_SQUARED_THRESHOLD = 0.6


def apply_fallback(
    con: duckdb.DuckDBPyConnection,
    evaluations: Mapping[str, EvaluationResult],
) -> int:
    """評価結果に基づき、品質基準を満たさない指標の予測値を no_prediction に更新する.

    Args:
        con: DuckDB 接続.
        evaluations: EvaluateModels の戻り値.

    Returns:
        no_prediction に変更したレコード数.
    """
    flagged = 0
    for indicator_id, evaluation in evaluations.items():
        if evaluation.r_squared >= R_SQUARED_THRESHOLD:
            continue
        # 該当指標 × 全都道府県 × 全 horizon の PredictedValue を no_prediction に
        cursor = con.execute(
            """
            UPDATE predicted_values
            SET quality_status = 'no_prediction',
                value = NULL,
                ci_lower = NULL,
                ci_upper = NULL,
                predicted_at = now()
            WHERE indicator_id = $1
              AND model_id = $2
            """,
            [indicator_id, evaluation.model_id],
        )
        # DuckDB Python API は execute後の rowcount を提供しないため、影響件数を別途数える
        (count,) = con.execute(
            """
            SELECT COUNT(*) FROM predicted_values
            WHERE indicator_id = $1 AND model_id = $2 AND quality_status = 'no_prediction'
            """,
            [indicator_id, evaluation.model_id],
        ).fetchone()
        flagged += int(count)
        logger.warning(
            f"fallback: {indicator_id} r2={evaluation.r_squared:.3f} < {R_SQUARED_THRESHOLD}; "
            f"flagged {count} predicted_values as no_prediction"
        )
        _ = cursor

    if flagged == 0:
        logger.info("apply_fallback: all indicators meet R^2 threshold")
    return flagged
