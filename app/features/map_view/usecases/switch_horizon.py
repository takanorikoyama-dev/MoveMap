"""SF-003 SwitchHorizon — 現在/3/5/10年を切替.

参照: outputs/06_system_design/05_画面設計.md (UX-D-03 ボタン推奨)
"""

from __future__ import annotations

from typing import Literal

import streamlit as st

Horizon = Literal["current", "3y", "5y", "10y"]

HORIZON_LABELS: dict[Horizon, str] = {
    "current": "現在",
    "3y": "3年後",
    "5y": "5年後",
    "10y": "10年後",
}


def switch_horizon() -> Horizon:
    """サイドバーで年次を選ばせる(スライダー不可、ボタン群).

    Returns:
        選択された horizon.
    """
    label_to_id: dict[str, Horizon] = {label: h for h, label in HORIZON_LABELS.items()}
    chosen_label = st.sidebar.radio(
        "年次選択",
        options=list(HORIZON_LABELS.values()),
        index=0,
        horizontal=False,
        key="selected_horizon_label",
    )
    return label_to_id[chosen_label]
