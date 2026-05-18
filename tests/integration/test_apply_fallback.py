"""TC-DP-14 ApplyFallback の統合テスト(INV-BIZ-003)."""

from __future__ import annotations

import duckdb

from app.features.data_pipeline.usecases.apply_fallback import R_SQUARED_THRESHOLD, apply_fallback
from app.features.data_pipeline.usecases.evaluate_models import EvaluationResult
from app.features.data_pipeline.usecases.generate_predictions import generate_predictions
from app.features.data_pipeline.usecases.retrain_models import retrain_models


def _evaluation(indicator_id: str, model_id: int, r2: float) -> EvaluationResult:
    return EvaluationResult(indicator_id=indicator_id, model_id=model_id, r_squared=r2, mae=1.0, n_samples=3)


def test_apply_fallback_marks_low_r2_as_no_prediction(db_with_history: duckdb.DuckDBPyConnection) -> None:
    state = retrain_models(db_with_history)
    generate_predictions(db_with_history, state)

    # price_index の R² を 0.3(閾値未満)とする
    evaluations = {
        "price_index": _evaluation("price_index", state.model_ids["price_index"], r2=0.3),
        "land_price": _evaluation("land_price", state.model_ids["land_price"], r2=0.9),
    }
    flagged = apply_fallback(db_with_history, evaluations)
    assert flagged > 0

    statuses = {row[0] for row in db_with_history.execute(
        "SELECT DISTINCT quality_status FROM predicted_values WHERE indicator_id = 'price_index'"
    ).fetchall()}
    assert statuses == {"no_prediction"}


def test_apply_fallback_keeps_good_quality_when_r2_high(db_with_history: duckdb.DuckDBPyConnection) -> None:
    state = retrain_models(db_with_history)
    generate_predictions(db_with_history, state)

    evaluations = {
        ind: _evaluation(ind, mid, r2=R_SQUARED_THRESHOLD + 0.1)
        for ind, mid in state.model_ids.items()
    }
    flagged = apply_fallback(db_with_history, evaluations)
    assert flagged == 0

    statuses = {row[0] for row in db_with_history.execute(
        "SELECT DISTINCT quality_status FROM predicted_values"
    ).fetchall()}
    assert statuses == {"good"}


def test_apply_fallback_zeroes_value_for_no_prediction(db_with_history: duckdb.DuckDBPyConnection) -> None:
    """no_prediction 化されたレコードは value/CI が NULL になる."""
    state = retrain_models(db_with_history)
    generate_predictions(db_with_history, state)

    evaluations = {
        "price_index": _evaluation("price_index", state.model_ids["price_index"], r2=0.1),
    }
    apply_fallback(db_with_history, evaluations)

    rows = db_with_history.execute(
        "SELECT value, ci_lower, ci_upper FROM predicted_values WHERE indicator_id = 'price_index'"
    ).fetchall()
    for value, lower, upper in rows:
        assert value is None
        assert lower is None
        assert upper is None
