"""Prophet 予測モデル.

参照: outputs/06_system_design/04_データ設計.md (prediction_models.model_type='prophet')
依存: prophet(pyproject に同梱、内部で pystan/cmdstanpy を使用)

データ不足時はフォールバック値を返す.
"""

from __future__ import annotations

from typing import Any

from app.shared.logger import get_logger

logger = get_logger(__name__)

MIN_OBSERVATIONS = 12


class InsufficientHistoryError(Exception):
    """学習に必要な観測点数が足りない."""


def train_prophet(history: list[tuple[str, float]]) -> dict[str, Any]:
    """履歴データから Prophet モデルを学習する.

    Args:
        history: [(measured_at_iso, value)].

    Returns:
        {"last_value": float, "n_obs": int, "fitted": Any | None, "ds_last": str}.

    Raises:
        InsufficientHistoryError: history が短すぎる.
    """
    if len(history) < MIN_OBSERVATIONS:
        raise InsufficientHistoryError(f"need >= {MIN_OBSERVATIONS} obs, got {len(history)}")

    values = [v for _, v in history]
    ds_last = history[-1][0]

    fitted_obj: Any = None
    try:
        import pandas as pd
        from prophet import Prophet  # type: ignore[import-not-found]

        df = pd.DataFrame({"ds": [t for t, _ in history], "y": values})
        model = Prophet(interval_width=0.8, daily_seasonality=False, weekly_seasonality=False)
        model.fit(df)
        fitted_obj = model
    except Exception:  # noqa: BLE001
        logger.exception("Prophet fit failed; falling back to naive last-value")

    return {
        "last_value": values[-1],
        "n_obs": len(history),
        "ds_last": ds_last,
        "fitted": fitted_obj,
    }


def forecast(
    model: dict[str, Any],
    horizon_years: int,
    points_per_year: int = 12,
) -> tuple[float, float, float]:
    """学習済み Prophet モデルから horizon 年先を予測する.

    Returns:
        (point_estimate, ci_lower, ci_upper). 80% CI.
    """
    steps = horizon_years * points_per_year
    fitted = model.get("fitted")
    if fitted is not None:
        try:
            future = fitted.make_future_dataframe(periods=steps, freq="MS")
            result = fitted.predict(future)
            tail = result.iloc[-1]
            return float(tail["yhat"]), float(tail["yhat_lower"]), float(tail["yhat_upper"])
        except Exception:  # noqa: BLE001
            logger.exception("Prophet forecast failed; using naive fallback")

    last = float(model["last_value"])
    return last, last * 0.9, last * 1.1
