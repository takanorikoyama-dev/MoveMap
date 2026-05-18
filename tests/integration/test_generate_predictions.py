"""TC-DP-13 GeneratePredictions の統合テスト."""

from __future__ import annotations

import duckdb

from app.features.data_pipeline.usecases.generate_predictions import HORIZONS, generate_predictions
from app.features.data_pipeline.usecases.retrain_models import retrain_models


def test_generate_predictions_creates_predicted_values(db_with_history: duckdb.DuckDBPyConnection) -> None:
    state = retrain_models(db_with_history)
    count = generate_predictions(db_with_history, state)

    # 4 indicators × 3 prefectures × 3 horizons = 36
    expected = 4 * 3 * len(HORIZONS)
    assert count == expected

    (rows,) = db_with_history.execute("SELECT COUNT(*) FROM predicted_values").fetchone()
    assert rows == expected


def test_generate_predictions_horizons_match_canonical_set(db_with_history: duckdb.DuckDBPyConnection) -> None:
    """horizon_years が {3, 5, 10} に限定される(INV-DATA-006)."""
    state = retrain_models(db_with_history)
    generate_predictions(db_with_history, state)

    horizons = {row[0] for row in db_with_history.execute(
        "SELECT DISTINCT horizon_years FROM predicted_values"
    ).fetchall()}
    assert horizons == {3, 5, 10}


def test_generate_predictions_initial_quality_good(db_with_history: duckdb.DuckDBPyConnection) -> None:
    """生成時点では全レコード quality_status='good'(フォールバックは別 Usecase)."""
    state = retrain_models(db_with_history)
    generate_predictions(db_with_history, state)

    statuses = {row[0] for row in db_with_history.execute(
        "SELECT DISTINCT quality_status FROM predicted_values"
    ).fetchall()}
    assert statuses == {"good"}
