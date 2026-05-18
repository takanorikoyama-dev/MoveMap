"""SF-004 ShowPrefectureDetail の単体テスト(マスタ辞書部分)."""

from __future__ import annotations

from app.features.map_view.usecases.show_prefecture_detail import PREFECTURE_NAMES


def test_prefecture_names_47() -> None:
    assert len(PREFECTURE_NAMES) == 47


def test_prefecture_names_specific_entries() -> None:
    assert PREFECTURE_NAMES["01"] == "北海道"
    assert PREFECTURE_NAMES["13"] == "東京都"
    assert PREFECTURE_NAMES["47"] == "沖縄県"


def test_prefecture_codes_are_zero_padded_two_digits() -> None:
    for code in PREFECTURE_NAMES:
        assert len(code) == 2
        assert code.isdigit()
        assert 1 <= int(code) <= 47
