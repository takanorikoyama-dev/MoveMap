"""SF-003 SwitchHorizon の単体テスト(辞書マッピング検証)."""

from __future__ import annotations

from app.features.map_view.usecases.switch_horizon import HORIZON_LABELS


def test_horizon_labels_four_entries() -> None:
    """現在/3年後/5年後/10年後 の 4 つ."""
    assert len(HORIZON_LABELS) == 4


def test_horizon_keys_match_canonical_set() -> None:
    assert set(HORIZON_LABELS.keys()) == {"current", "3y", "5y", "10y"}


def test_horizon_default_is_current() -> None:
    """先頭の選択肢が「現在」になる前提."""
    first_key = next(iter(HORIZON_LABELS))
    assert first_key == "current"
