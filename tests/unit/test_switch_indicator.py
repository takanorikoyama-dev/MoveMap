"""SF-002 SwitchIndicator の単体テスト(辞書マッピング検証).

実際の Streamlit UI は smoke で別途検証.
"""

from __future__ import annotations

from app.features.map_view.usecases.switch_indicator import INDICATOR_LABELS


def test_indicator_labels_contains_nine_entries() -> None:
    """9 指標すべてに表示ラベルが定義されている(2026-05-26 治安+人口流入追加)."""
    assert len(INDICATOR_LABELS) == 9


def test_indicator_labels_keys_match_seeds() -> None:
    """ラベルキーが seeds/indicators.csv の id と一致する."""
    expected = {
        "price_index",
        "land_price",
        "rent_index",
        "birth_count",
        "air_quality",
        "disaster_risk",
        "transport_access",
        "public_safety",
        "net_migration",
    }
    assert set(INDICATOR_LABELS.keys()) == expected


def test_label_to_id_mapping_is_bijective() -> None:
    """逆引き辞書を作っても重複しない(label が一意)."""
    label_to_id = {label: indicator for indicator, label in INDICATOR_LABELS.items()}
    assert len(label_to_id) == 9
