"""ranking.py ユニットテスト.

検証範囲:
- 方向ロジック(HIGHER_IS_BETTER / LOWER_IS_BETTER)
- 偏差値計算(direction 反映、None 保持、std=0 ハンドリング)
- 星マッピング(70+→5, 60-70→4, ..., <30→0)
- compute_ranking の出力構造(47件、降順、None は末尾)
- stars_to_unicode の文字列フォーマット
"""

from __future__ import annotations

from app.features.map_view.ranking import (
    ALL_INDICATORS,
    HIGHER_IS_BETTER,
    LOWER_IS_BETTER,
    _compute_deviation_scores,
    _direction,
    _stars_from_score,
    compute_ranking,
    stars_to_unicode,
)


def test_direction_higher_is_better() -> None:
    assert _direction("birth_count") == 1
    assert _direction("transport_access") == 1


def test_direction_lower_is_better() -> None:
    assert _direction("price_index") == -1
    assert _direction("land_price") == -1
    assert _direction("rent_index") == -1
    assert _direction("air_quality") == -1
    assert _direction("disaster_risk") == -1


def test_direction_unknown_defaults_to_positive() -> None:
    assert _direction("unknown_indicator") == 1


def test_all_indicators_covered_by_direction_sets() -> None:
    """ALL_INDICATORS の各要素は HIGHER または LOWER のいずれかに属する."""
    for ind in ALL_INDICATORS:
        assert ind in HIGHER_IS_BETTER or ind in LOWER_IS_BETTER, (
            f"{ind} に住みやすさ方向が定義されていない"
        )


def test_stars_from_score_thresholds() -> None:
    assert _stars_from_score(None) == 0
    assert _stars_from_score(75.0) == 5
    assert _stars_from_score(70.0) == 5
    assert _stars_from_score(69.9) == 4
    assert _stars_from_score(60.0) == 4
    assert _stars_from_score(55.0) == 3
    assert _stars_from_score(50.0) == 3
    assert _stars_from_score(45.0) == 2
    assert _stars_from_score(35.0) == 1
    assert _stars_from_score(29.9) == 0


def test_compute_deviation_higher_is_better() -> None:
    """direction=+1: 平均より高い値が偏差値 50 超."""
    values: dict[str, float | None] = {"01": 100.0, "02": 200.0, "03": 300.0}
    scores = _compute_deviation_scores(values, direction=1)
    # 平均 200, 偏差値 50 を中心に、300 が高、100 が低
    assert scores["02"] is not None and abs(scores["02"] - 50.0) < 0.01
    assert scores["03"] is not None and scores["03"] > 50.0
    assert scores["01"] is not None and scores["01"] < 50.0


def test_compute_deviation_lower_is_better() -> None:
    """direction=-1: 平均より低い値が偏差値 50 超."""
    values: dict[str, float | None] = {"01": 100.0, "02": 200.0, "03": 300.0}
    scores = _compute_deviation_scores(values, direction=-1)
    assert scores["01"] is not None and scores["01"] > 50.0
    assert scores["02"] is not None and abs(scores["02"] - 50.0) < 0.01
    assert scores["03"] is not None and scores["03"] < 50.0


def test_compute_deviation_preserves_none() -> None:
    values: dict[str, float | None] = {"01": 10.0, "02": None, "03": 30.0}
    scores = _compute_deviation_scores(values, direction=1)
    assert scores["02"] is None
    assert scores["01"] is not None
    assert scores["03"] is not None


def test_compute_deviation_all_same_values_returns_50() -> None:
    """全値同一(std=0)の場合は偏差値 50."""
    values: dict[str, float | None] = {"01": 100.0, "02": 100.0, "03": 100.0}
    scores = _compute_deviation_scores(values, direction=1)
    for v in scores.values():
        assert v == 50.0


def test_compute_deviation_handles_too_few_values() -> None:
    """有効値が 2 未満なら全部 50 か None."""
    values: dict[str, float | None] = {"01": 10.0, "02": None, "03": None}
    scores = _compute_deviation_scores(values, direction=1)
    assert scores["01"] == 50.0
    assert scores["02"] is None
    assert scores["03"] is None


def test_stars_to_unicode_format() -> None:
    assert stars_to_unicode(5) == "★★★★★"
    assert stars_to_unicode(3) == "★★★☆☆"
    assert stars_to_unicode(0) == "☆☆☆☆☆"
    # クランプ
    assert stars_to_unicode(-1) == "☆☆☆☆☆"
    assert stars_to_unicode(10) == "★★★★★"


def test_compute_ranking_returns_47_prefectures() -> None:
    ranks = compute_ranking(horizon="current")
    assert len(ranks) == 47


def test_compute_ranking_sorted_descending_with_none_last() -> None:
    ranks = compute_ranking(horizon="current")
    # None は末尾に
    valid_scores = [r.composite_score for r in ranks if r.composite_score is not None]
    none_scores = [r.composite_score for r in ranks if r.composite_score is None]
    # 並びは「valid (降順) → None」
    assert ranks[: len(valid_scores)] == [r for r in ranks if r.composite_score is not None]
    assert ranks[len(valid_scores) :] == [r for r in ranks if r.composite_score is None]
    # valid_scores が降順
    assert valid_scores == sorted(valid_scores, reverse=True)
    # 構造的に none_scores の数は使用後 OK(silencing unused-warn)
    assert len(none_scores) >= 0


def test_compute_ranking_stars_match_composite() -> None:
    """各 PrefectureRank の stars が composite_score から導出されている."""
    ranks = compute_ranking(horizon="current")
    for r in ranks:
        assert r.stars == _stars_from_score(r.composite_score)


def test_compute_ranking_per_indicator_keys_complete() -> None:
    """per_indicator_value / per_indicator_score に 7 指標すべて含まれる."""
    ranks = compute_ranking(horizon="current")
    for r in ranks:
        assert set(r.per_indicator_value.keys()) == set(ALL_INDICATORS)
        assert set(r.per_indicator_score.keys()) == set(ALL_INDICATORS)
