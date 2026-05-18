"""予測モデル関連エンティティ(Aggregate Root: Prediction)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal

ModelType = Literal["arima", "sarima", "prophet"]


@dataclass(frozen=True, slots=True)
class PredictionModel:
    id: int
    indicator_id: str
    model_type: ModelType
    trained_at: datetime
    parameters: dict[str, Any]
    features_used: list[str]
    training_data_range: dict[str, str]  # {"from": "YYYY-MM-DD", "to": "..."}


@dataclass(frozen=True, slots=True)
class ModelEvaluation:
    """append-only."""

    id: int
    model_id: int
    r_squared: float
    mae: float
    evaluated_at: datetime
    evaluation_period: dict[str, str]
