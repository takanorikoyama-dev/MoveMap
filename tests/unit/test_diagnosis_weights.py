"""移住タイプ診断: 重み算出ロジックの単体テスト."""

from __future__ import annotations

from app.features.map_view.usecases.show_diagnosis import (
    DiagnosisAnswers,
    _compute_weights,
)


def _ans(**kwargs):  # type: ignore[no-untyped-def]
    """テスト用のヘルパー(デフォルト値あり)."""
    defaults = {
        "family": "couple",
        "work_style": "retired",
        "rent_budget": "mid",
        "avoid": (),
        "priorities": (),
    }
    defaults.update(kwargs)
    return DiagnosisAnswers(**defaults)


def test_weights_are_within_0_to_100() -> None:
    """すべての回答パターンで重みは 0〜100 の範囲."""
    cases = [
        _ans(),
        _ans(family="family", work_style="local_job", rent_budget="low",
             avoid=("disaster", "expensive", "medical", "transport", "unsafe"),
             priorities=("clean_air", "future_active", "good_access", "low_cost", "safe")),
        _ans(family="solo", work_style="remote", rent_budget="vip"),
        _ans(family="multi_gen", work_style="startup"),
    ]
    for ans in cases:
        weights = _compute_weights(ans)
        for ind, w in weights.items():
            assert 0.0 <= w <= 100.0, f"{ind}={w} out of range for {ans}"


def test_unsafe_avoidance_boosts_public_safety_weight() -> None:
    """避けたい=治安への不安 を選ぶと public_safety の重みが上がる."""
    base = _compute_weights(_ans())
    with_avoid = _compute_weights(_ans(avoid=("unsafe",)))
    assert with_avoid["public_safety"] > base["public_safety"]


def test_safe_priority_boosts_public_safety_weight() -> None:
    """重視=治安が良い を選ぶと public_safety の重みが上がる."""
    base = _compute_weights(_ans())
    with_safe = _compute_weights(_ans(priorities=("safe",)))
    assert with_safe["public_safety"] > base["public_safety"]


def test_family_emphasizes_public_safety_too() -> None:
    """子育てファミリーは治安重視(public_safety がアップ)."""
    couple = _compute_weights(_ans(family="couple"))
    family = _compute_weights(_ans(family="family"))
    assert family["public_safety"] > couple["public_safety"]


def test_disaster_avoidance_boosts_disaster_risk_weight() -> None:
    """避けたい=災害 を選ぶと disaster_risk の重みが上がる."""
    base = _compute_weights(_ans())
    with_avoid = _compute_weights(_ans(avoid=("disaster",)))
    assert with_avoid["disaster_risk"] > base["disaster_risk"]


def test_low_budget_boosts_rent_and_price_weight() -> None:
    base = _compute_weights(_ans(rent_budget="vip"))
    low = _compute_weights(_ans(rent_budget="low"))
    assert low["rent_index"] > base["rent_index"]
    assert low["price_index"] > base["price_index"]


def test_family_with_kids_emphasizes_birth_disaster_air() -> None:
    couple = _compute_weights(_ans(family="couple"))
    family = _compute_weights(_ans(family="family"))
    assert family["birth_count"] > couple["birth_count"]
    assert family["disaster_risk"] > couple["disaster_risk"]
    assert family["air_quality"] > couple["air_quality"]


def test_retired_emphasizes_cost_and_air_quality() -> None:
    retired = _compute_weights(_ans(work_style="retired"))
    local = _compute_weights(_ans(work_style="local_job"))
    assert retired["price_index"] > local["price_index"]
    assert retired["air_quality"] > local["air_quality"]
    # 一方で local_job は出生数(地域活気)に高い重み
    assert local["birth_count"] > retired["birth_count"]


def test_priorities_boost_specific_indicators() -> None:
    base = _compute_weights(_ans())
    with_clean = _compute_weights(_ans(priorities=("clean_air",)))
    with_access = _compute_weights(_ans(priorities=("good_access",)))
    assert with_clean["air_quality"] > base["air_quality"]
    assert with_access["transport_access"] > base["transport_access"]


def test_weights_cover_all_9_indicators() -> None:
    """9 指標すべてに重みが付く(2026-05-26 治安+人口流入追加)."""
    weights = _compute_weights(_ans())
    expected = {"price_index", "land_price", "rent_index", "birth_count",
                "air_quality", "disaster_risk", "transport_access",
                "public_safety", "net_migration"}
    assert set(weights.keys()) == expected
