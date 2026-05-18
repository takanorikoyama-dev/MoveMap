"""TC-DP-11 RetrainModels の統合テスト."""

from __future__ import annotations

import duckdb

from app.features.data_pipeline.usecases.retrain_models import (
    PREDICTABLE_INDICATORS,
    retrain_models,
)


def test_retrain_models_creates_prediction_models_for_predictable(db_with_history: duckdb.DuckDBPyConnection) -> None:
    """主要4指標について prediction_models が 1 行ずつ作成される."""
    state = retrain_models(db_with_history)
    assert set(state.model_ids.keys()) == set(PREDICTABLE_INDICATORS)
    assert len(state.model_ids) == 4

    (count,) = db_with_history.execute("SELECT COUNT(*) FROM prediction_models").fetchone()
    assert count == 4


def test_retrain_models_fitted_state_per_prefecture(db_with_history: duckdb.DuckDBPyConnection) -> None:
    """fitted dict が指標 × 都道府県 で埋まる."""
    state = retrain_models(db_with_history)
    for ind in PREDICTABLE_INDICATORS:
        assert ind in state.fitted
        # fixture は 3 都道府県 × 24 観測 = 学習可能
        assert len(state.fitted[ind]) == 3


def test_retrain_models_skips_indicator_without_history(db: duckdb.DuckDBPyConnection) -> None:
    """履歴がない指標は model_ids に含まれない."""
    state = retrain_models(db)
    assert state.model_ids == {}
