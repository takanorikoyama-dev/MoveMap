"""値オブジェクト群(CurrentValue / HistoricalValue / PredictedValue).

集約 RegionMeasurement / Prediction のメンバ.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Literal

ValueStatus = Literal["active", "missing", "stale"]
QualityStatus = Literal["good", "no_prediction"]
HorizonYears = Literal[3, 5, 10]


@dataclass(frozen=True, slots=True)
class CurrentValue:
    prefecture_code: str
    indicator_id: str
    value: float | None
    measured_at: date | None
    updated_at: datetime
    status: ValueStatus


@dataclass(frozen=True, slots=True)
class HistoricalValue:
    """append-only。INV-DATA-007 によりこのインスタンスは不変."""

    id: int
    prefecture_code: str
    indicator_id: str
    value: float
    measured_at: date
    recorded_at: datetime


@dataclass(frozen=True, slots=True)
class PredictedValue:
    prefecture_code: str
    indicator_id: str
    horizon_years: HorizonYears
    value: float | None
    ci_lower: float | None
    ci_upper: float | None
    quality_status: QualityStatus
    model_id: int | None
    predicted_at: datetime
