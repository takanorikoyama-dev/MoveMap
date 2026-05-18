"""指標エンティティ(Aggregate Root: IndicatorAggregate)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Category = Literal["must", "should", "could"]


@dataclass(frozen=True, slots=True)
class Indicator:
    id: str
    name_ja: str
    name_en: str
    unit: str
    category: Category
    is_predictable: bool
    source_id: str
