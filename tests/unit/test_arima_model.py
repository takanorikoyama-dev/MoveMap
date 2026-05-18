"""ARIMA モデルの単体テスト."""

from __future__ import annotations

import math

import pytest

from app.features.data_pipeline.models import arima


def _gen_history(n: int) -> list[tuple[str, float]]:
    return [(f"2024-{i % 12 + 1:02d}-01", 100.0 + i * 0.5) for i in range(n)]


def test_train_arima_raises_for_short_history() -> None:
    with pytest.raises(arima.InsufficientHistoryError):
        arima.train_arima(_gen_history(5))


def test_train_arima_returns_model_dict() -> None:
    model = arima.train_arima(_gen_history(24))
    assert model["n_obs"] == 24
    assert "order" in model
    assert "last_value" in model
    # fitted は statsmodels が利用可能なら non-None
    # ない場合でも last_value フォールバックで forecast は動く


def test_forecast_returns_three_tuple() -> None:
    model = arima.train_arima(_gen_history(24))
    point, lower, upper = arima.forecast(model, horizon_years=3)
    assert isinstance(point, float)
    # 信頼区間は point を含む(両端のいずれか or 両方が point の近傍)
    assert lower <= upper or math.isclose(lower, upper, rel_tol=1e-9)


def test_forecast_fallback_for_naive_model() -> None:
    """fitted=None の状態でも naive forecast(最終値固定 + std)が返る."""
    model = {"last_value": 100.0, "residual_std": 1.0, "fitted": None}
    point, lower, upper = arima.forecast(model, horizon_years=5)
    assert point == 100.0
    assert lower < point < upper
