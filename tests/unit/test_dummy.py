"""map_view ダミーデータ生成の単体テスト."""

from __future__ import annotations

from app.features.map_view.dummy import (
    INDICATOR_RANGES,
    PREDICTABLE_INDICATORS,
    PREF_CODES,
    dummy_value,
    dummy_values_for,
)


def test_pref_codes_47() -> None:
    assert len(PREF_CODES) == 47
    assert PREF_CODES[0] == "01"
    assert PREF_CODES[-1] == "47"


def test_dummy_value_is_deterministic() -> None:
    """同じ key は同じ値."""
    v1 = dummy_value("price_index", "13", "current")
    v2 = dummy_value("price_index", "13", "current")
    assert v1 == v2


def test_dummy_value_within_range() -> None:
    lo, hi = INDICATOR_RANGES["price_index"]
    v = dummy_value("price_index", "13", "current")
    assert v is not None
    assert lo - 1 <= v <= hi + 1  # 多少の drift を許容


def test_dummy_value_no_prediction_for_non_predictable() -> None:
    """予測対象外の指標 × 未来時点は None."""
    assert dummy_value("air_quality", "13", "current") is not None
    assert dummy_value("air_quality", "13", "3y") is None
    assert dummy_value("disaster_risk", "13", "5y") is None
    assert dummy_value("transport_access", "13", "10y") is None


def test_dummy_value_predictable_returns_value_at_future() -> None:
    """主要4指標は未来時点でも値が返る."""
    for ind in PREDICTABLE_INDICATORS:
        v = dummy_value(ind, "13", "5y")
        assert v is not None


def test_dummy_values_for_returns_47() -> None:
    values = dummy_values_for("price_index", "current")
    assert len(values) == 47
    assert set(values.keys()) == set(PREF_CODES)
