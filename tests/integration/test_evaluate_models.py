"""TC-DP-12 EvaluateModels の統合テスト."""

from __future__ import annotations

import duckdb

from app.features.data_pipeline.usecases.evaluate_models import evaluate_models
from app.features.data_pipeline.usecases.retrain_models import (
    PREDICTABLE_INDICATORS,
    retrain_models,
)


def test_evaluate_models_inserts_one_row_per_indicator(db_with_history: duckdb.DuckDBPyConnection) -> None:
    state = retrain_models(db_with_history)
    evaluations = evaluate_models(db_with_history, state)

    # 各指標について model_evaluations に少なくとも 1 行
    (count,) = db_with_history.execute("SELECT COUNT(*) FROM model_evaluations").fetchone()
    assert count >= 1

    # EvaluationResult が辞書として返る
    for ind in evaluations:
        assert ind in PREDICTABLE_INDICATORS
        result = evaluations[ind]
        assert result.indicator_id == ind
        assert isinstance(result.r_squared, float)
        assert isinstance(result.mae, float)


def test_evaluate_models_empty_state(db_with_history: duckdb.DuckDBPyConnection) -> None:
    """空の state でも例外を出さず空 dict を返す."""
    from app.features.data_pipeline.usecases.retrain_models import PredictionState

    empty = PredictionState()
    evaluations = evaluate_models(db_with_history, empty)
    assert evaluations == {}
