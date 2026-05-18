"""SF-002 SwitchIndicator — 7指標から1つを選び返す.

参照: outputs/06_system_design/05_画面設計.md (SCR-001 指標切替)
"""

from __future__ import annotations

from typing import Literal

import streamlit as st

IndicatorId = Literal[
    "price_index",
    "land_price",
    "rent_index",
    "birth_count",
    "air_quality",
    "disaster_risk",
    "transport_access",
]

INDICATOR_LABELS: dict[IndicatorId, str] = {
    "price_index": "物価指数",
    "land_price": "地価",
    "rent_index": "賃料相場",
    "birth_count": "出生数",
    "air_quality": "空気質(PM2.5)",
    "disaster_risk": "災害リスク",
    "transport_access": "交通アクセス",
}


def switch_indicator() -> IndicatorId:
    """サイドバーで指標を選ばせ、選択中の indicator_id を返す.

    Returns:
        選択された indicator_id.
    """
    label_to_id: dict[str, IndicatorId] = {label: ind for ind, label in INDICATOR_LABELS.items()}

    chosen_label = st.sidebar.radio(
        "指標選択",
        options=list(INDICATOR_LABELS.values()),
        index=0,
        key="selected_indicator_label",
    )
    return label_to_id[chosen_label]
