"""都道府県別ランキング + 総合偏差値の計算ロジック.

設計判断:
    各指標には「住みやすさ」観点で 望ましい方向 がある.
    - HIGHER_IS_BETTER: 値が高いほど良い(出生数 = 地域の将来性、交通アクセス = 利便性)
    - LOWER_IS_BETTER: 値が低いほど良い(物価/地価/賃料 = 生活コスト、空気質 PM2.5 / 災害リスク = 健康・安全)

偏差値:
    各指標について 47 都道府県の平均・標準偏差から Z スコアを算出.
    偏差値 = 50 + 10 × Z × direction(direction = +1 か -1)
    LOWER_IS_BETTER の場合 direction = -1(低い値が高偏差値になる)

総合偏差値:
    7 指標の偏差値の平均(等加重). データなしの指標は除外.

★(星):
    総合偏差値を 5 段階に離散化.
    70+: ★5、60-70: ★4、50-60: ★3、40-50: ★2、30-40: ★1、30 未満: ★0
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass
from typing import Literal

from app.features.map_view.data_provider import values_for_all_indicators

# 値の方向(住みやすさ観点)
HIGHER_IS_BETTER: frozenset[str] = frozenset(
    {"birth_count", "transport_access", "net_migration"}
)
LOWER_IS_BETTER: frozenset[str] = frozenset(
    {"price_index", "land_price", "rent_index", "air_quality", "disaster_risk", "public_safety"}
)

ALL_INDICATORS: tuple[str, ...] = (
    "price_index",
    "land_price",
    "rent_index",
    "birth_count",
    "air_quality",
    "disaster_risk",
    "transport_access",
    "public_safety",
    "net_migration",
)

Horizon = Literal["current", "3y", "5y", "10y"]


@dataclass(frozen=True, slots=True)
class PrefectureRank:
    prefecture_code: str
    prefecture_name: str
    per_indicator_value: dict[str, float | None]    # 元の指標値
    per_indicator_score: dict[str, float | None]    # 偏差値(direction 反映済み)
    composite_score: float | None                   # 総合偏差値(7 指標平均)
    stars: int                                      # 0〜5


def _direction(indicator_id: str) -> int:
    """+1: 高いほど良い、-1: 低いほど良い."""
    if indicator_id in HIGHER_IS_BETTER:
        return 1
    if indicator_id in LOWER_IS_BETTER:
        return -1
    return 1


def _stars_from_score(score: float | None) -> int:
    """総合偏差値 → 0-5 星."""
    if score is None:
        return 0
    if score >= 70:
        return 5
    if score >= 60:
        return 4
    if score >= 50:
        return 3
    if score >= 40:
        return 2
    if score >= 30:
        return 1
    return 0


def _compute_deviation_scores(values_by_pref: dict[str, float | None], direction: int) -> dict[str, float | None]:
    """{pref_code: value} → {pref_code: 偏差値}.

    None は None として保持. std=0(全値同一)の場合は 50 を返す.
    """
    valid = [v for v in values_by_pref.values() if v is not None]
    if len(valid) < 2:
        return {code: (50.0 if val is not None else None) for code, val in values_by_pref.items()}

    mean = statistics.fmean(valid)
    std = statistics.pstdev(valid)
    result: dict[str, float | None] = {}
    for code, value in values_by_pref.items():
        if value is None:
            result[code] = None
        elif std == 0:
            result[code] = 50.0
        else:
            z = (value - mean) / std
            result[code] = 50.0 + 10.0 * z * direction
    return result


def compute_ranking(
    horizon: Horizon = "current",
    weights: dict[str, float] | None = None,
) -> list[PrefectureRank]:
    """全 47 都道府県の指標値 + 偏差値 + 総合偏差値 + 星 を計算する.

    Args:
        horizon: 集計対象の時点(現在 or 予測).
        weights: {indicator_id: weight} の重み(正の数). None なら等加重平均.
            指定された場合は正規化(合計1)して加重平均.

    Returns:
        PrefectureRank のリスト(総合偏差値の降順、Noneは末尾).
    """
    from app.features.map_view.usecases.show_prefecture_detail import PREFECTURE_NAMES

    # 重みの正規化(指定された指標のみ採用、合計1にスケール)
    effective_weights: dict[str, float] | None = None
    if weights:
        positive = {k: float(v) for k, v in weights.items() if k in ALL_INDICATORS and float(v) > 0}
        total = sum(positive.values())
        if total > 0:
            effective_weights = {k: v / total for k, v in positive.items()}

    # 全 9 指標 × 47 都道府県を 1 DB 接続でまとめて取得(パフォーマンス改善)
    indicator_values = values_for_all_indicators(ALL_INDICATORS, horizon)
    indicator_scores: dict[str, dict[str, float | None]] = {}
    for ind in ALL_INDICATORS:
        indicator_scores[ind] = _compute_deviation_scores(indicator_values[ind], _direction(ind))

    # 都道府県別に集計
    ranks: list[PrefectureRank] = []
    for code, name in PREFECTURE_NAMES.items():
        per_value = {ind: indicator_values[ind].get(code) for ind in ALL_INDICATORS}
        per_score = {ind: indicator_scores[ind].get(code) for ind in ALL_INDICATORS}
        composite = _aggregate_composite(per_score, effective_weights)
        ranks.append(
            PrefectureRank(
                prefecture_code=code,
                prefecture_name=name,
                per_indicator_value=per_value,
                per_indicator_score=per_score,
                composite_score=composite,
                stars=_stars_from_score(composite),
            )
        )

    # 総合偏差値の降順、None は最下位
    ranks.sort(key=lambda r: (r.composite_score is None, -(r.composite_score or 0.0)))
    return ranks


def _aggregate_composite(
    per_score: dict[str, float | None],
    weights: dict[str, float] | None,
) -> float | None:
    """偏差値辞書 → 総合偏差値. None値は集計対象外、weights があれば加重平均."""
    if weights:
        weighted_sum = 0.0
        weight_sum = 0.0
        for ind, w in weights.items():
            s = per_score.get(ind)
            if s is None:
                continue
            weighted_sum += s * w
            weight_sum += w
        return weighted_sum / weight_sum if weight_sum > 0 else None
    valid = [s for s in per_score.values() if s is not None]
    return statistics.fmean(valid) if valid else None


def stars_to_unicode(stars: int, max_stars: int = 5) -> str:
    """0-5 を ★★★☆☆ 形式の文字列に."""
    stars = max(0, min(max_stars, int(stars)))
    return "★" * stars + "☆" * (max_stars - stars)


__all__ = [
    "ALL_INDICATORS",
    "HIGHER_IS_BETTER",
    "LOWER_IS_BETTER",
    "PrefectureRank",
    "compute_ranking",
    "stars_to_unicode",
]
