"""ダミーデータ生成(UI 動作確認用).

Wave 2 / 予測モデル実装完了後に削除し、DB クエリに置き換える.
"""

from __future__ import annotations

import hashlib

PREF_CODES: tuple[str, ...] = tuple(f"{i:02d}" for i in range(1, 48))
HORIZONS: tuple[str, ...] = ("current", "3y", "5y", "10y")

# 指標ごとに期待される値レンジ(視覚的に意味があるダミーのため).
INDICATOR_RANGES: dict[str, tuple[float, float]] = {
    "price_index": (95.0, 110.0),
    "land_price": (50_000.0, 1_500_000.0),
    "rent_index": (90.0, 130.0),
    "birth_count": (5.0, 12.0),
    "air_quality": (5.0, 25.0),
    "disaster_risk": (1.0, 5.0),
    "transport_access": (1.0, 5.0),
}

PREDICTABLE_INDICATORS = frozenset({"price_index", "land_price", "rent_index", "birth_count"})


def _hash_to_unit(*parts: str) -> float:
    """文字列を [0, 1) に決定的にマップ."""
    digest = hashlib.md5("|".join(parts).encode("utf-8")).hexdigest()
    return int(digest[:8], 16) / 0xFFFFFFFF


def dummy_value(indicator_id: str, prefecture_code: str, horizon: str) -> float | None:
    """指定指標 × 都道府県 × 年次のダミー値.

    - 予測対象外指標(air_quality / disaster_risk / transport_access)は horizon != current で None.
    - 同じキーは常に同じ値(deterministic).
    """
    if horizon != "current" and indicator_id not in PREDICTABLE_INDICATORS:
        return None

    lo, hi = INDICATOR_RANGES.get(indicator_id, (0.0, 100.0))
    base = _hash_to_unit(indicator_id, prefecture_code)
    drift = _hash_to_unit(indicator_id, prefecture_code, horizon) * 0.1 - 0.05  # ±5%
    raw = base + drift
    return lo + max(0.0, min(1.0, raw)) * (hi - lo)


def dummy_values_for(indicator_id: str, horizon: str) -> dict[str, float | None]:
    """47都道府県分のダミー値を辞書で返す."""
    return {code: dummy_value(indicator_id, code, horizon) for code in PREF_CODES}
