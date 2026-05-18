"""都道府県エンティティ(Aggregate Root: RegionMeasurement)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Prefecture:
    code: str  # JIS X 0401, 2-digit
    name_ja: str
    name_en: str
    region: str
    centroid_lat: float
    centroid_lon: float
