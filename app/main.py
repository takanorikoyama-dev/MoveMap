"""Streamlit エントリポイント.

Phase 7 Wave 1+ 段階. ダミーデータで MAP UI 全体フローが動作する.
"""

from __future__ import annotations

import streamlit as st

from app.features.compliance.disclaimer import render as render_disclaimer
from app.features.compliance.show_data_sources import show_data_sources
from app.features.map_view.components.status_panel import render_status_panel
from app.features.map_view.usecases.show_map import show_map
from app.features.map_view.usecases.show_model_detail import show_model_detail
from app.features.map_view.usecases.show_prefecture_detail import (
    PREFECTURE_NAMES,
    show_prefecture_detail,
)
from app.features.map_view.usecases.show_ranking import show_ranking
from app.features.map_view.usecases.switch_horizon import HORIZON_LABELS, switch_horizon
from app.features.map_view.usecases.switch_indicator import INDICATOR_LABELS, switch_indicator

st.set_page_config(
    page_title="MoveMap — 地方移住MAP",
    page_icon="🗾",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("MoveMap — 地方移住MAP")
render_disclaimer()

indicator_id = switch_indicator()
horizon = switch_horizon()

st.sidebar.markdown("---")
st.sidebar.caption(
    f"選択中: **{INDICATOR_LABELS[indicator_id]}** / **{HORIZON_LABELS[horizon]}**"
)

# データ状態パネル(運用透明性)
render_status_panel()

tab_map, tab_ranking, tab_detail, tab_model = st.tabs(
    ["MAP", "ランキング", "都道府県詳細", "モデル根拠"]
)

with tab_map:
    show_map(indicator_id, horizon)

with tab_ranking:
    show_ranking(horizon)

with tab_detail:
    pref_options = [f"{code} {name}" for code, name in PREFECTURE_NAMES.items()]
    chosen = st.selectbox(
        "都道府県を選択",
        options=pref_options,
        index=12,  # default: 東京都
        key="selected_prefecture",
    )
    chosen_code = chosen.split(" ", 1)[0]
    show_prefecture_detail(chosen_code)

with tab_model:
    show_model_detail(indicator_id)

st.markdown("---")
show_data_sources(None)
