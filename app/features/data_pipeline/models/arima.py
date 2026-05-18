"""ARIMA / SARIMA 予測モデル(statsmodels).

参照: outputs/06_system_design/04_データ設計.md (prediction_models.model_type='arima')
依存: statsmodels(pyproject に同梱)

データ不足時(履歴 < MIN_OBSERVATIONS)はフォールバック値を返し、上流で no_prediction として扱う.
"""

from __future__ import annotations

from typing import Any

from app.shared.logger import get_logger

logger = get_logger(__name__)

MIN_OBSERVATIONS = 12  # ARIMA(2,1,2) には最低限の観測点が必要
DEFAULT_ORDER: tuple[int, int, int] = (2, 1, 2)


class InsufficientHistoryError(Exception):
    """学習に必要な観測点数が足りない."""


def train_arima(
    history: list[tuple[str, float]],
    order: tuple[int, int, int] = DEFAULT_ORDER,
) -> dict[str, Any]:
    """履歴データから ARIMA モデルを学習する.

    Args:
        history: [(measured_at_iso, value)] — 時系列順.
        order: ARIMA(p, d, q).

    Returns:
        {"order": tuple, "params": list, "last_value": float, "residual_std": float,
         "n_obs": int, "fitted": Any | None}.
        `fitted` は statsmodels が利用不能な環境では None.

    Raises:
        InsufficientHistoryError: history が短すぎる.
    """
    if len(history) < MIN_OBSERVATIONS:
        raise InsufficientHistoryError(f"need >= {MIN_OBSERVATIONS} obs, got {len(history)}")

    values = [v for _, v in history]
    last_value = values[-1]

    fitted_obj: Any = None
    params: list[float] = []
    residual_std = 0.0
    try:
        from statsmodels.tsa.arima.model import ARIMA  # type: ignore[import-not-found]

        model = ARIMA(values, order=order)
        result = model.fit()
        fitted_obj = result
        params = list(map(float, result.params))
        residual_std = float(result.resid.std())
    except Exception:  # noqa: BLE001 - statsmodels の細かい例外を吸収
        logger.exception("ARIMA fit failed; falling back to naive last-value")

    return {
        "order": order,
        "params": params,
        "last_value": last_value,
        "residual_std": residual_std,
        "n_obs": len(history),
        "fitted": fitted_obj,
    }


def forecast(
    model: dict[str, Any],
    horizon_years: int,
    points_per_year: int = 12,
) -> tuple[float, float, float]:
    """学習済みモデルから horizon 年先を予測する.

    Args:
        model: train_arima の戻り値.
        horizon_years: 予測したい年数(3/5/10 を想定).
        points_per_year: 1 年の観測点数(月次なら 12).

    Returns:
        (point_estimate, ci_lower, ci_upper). CI は 80% を採用.
    """
    steps = horizon_years * points_per_year

    fitted = model.get("fitted")
    if fitted is not None:
        try:
            result = fitted.get_forecast(steps=steps)
            mean = float(result.predicted_mean[-1])
            ci = result.conf_int(alpha=0.2)  # 80% CI
            lower = float(ci[-1, 0])
            upper = float(ci[-1, 1])
            return mean, lower, upper
        except Exception:  # noqa: BLE001
            logger.exception("statsmodels forecast failed; using naive fallback")

    # フォールバック: 最終値固定 + 残差 std を CI とみなす
    last = float(model["last_value"])
    sigma = float(model.get("residual_std", 0.0))
    return last, last - 1.28 * sigma, last + 1.28 * sigma
