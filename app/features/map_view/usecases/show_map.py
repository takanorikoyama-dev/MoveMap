"""SF-001 ShowMap — 47都道府県の選択中指標・年次でヒートマップ描画.

参照: outputs/06_system_design/05_画面設計.md (SCR-001)
データ源: app.features.map_view.data_provider 経由(DB → dummy フォールバック)
"""

from __future__ import annotations

from typing import Literal

import streamlit as st

from app.features.map_view.components.heatmap import AnnotationMode, render_choropleth
from app.features.map_view.data_provider import values_for
from app.features.map_view.usecases.switch_horizon import HORIZON_LABELS
from app.features.map_view.usecases.switch_indicator import INDICATOR_LABELS, IndicatorId

Horizon = Literal["current", "3y", "5y", "10y"]

_ANNOTATION_OPTIONS: dict[str, AnnotationMode] = {
    "OFF(地図のみ)": "off",
    "上位5+下位5 を引き出し線で表示": "extremes",
    "47都道府県すべて表示": "all",
}


def show_map(indicator_id: IndicatorId, horizon: Horizon) -> None:
    """選択中の指標・年次で MAP を描画する.

    Args:
        indicator_id: 表示する指標 ID.
        horizon: 現在 or 予測時点.
    """
    indicator_label = INDICATOR_LABELS[indicator_id]
    horizon_label = HORIZON_LABELS[horizon]

    # ラベル表示モード切替
    chosen_label = st.radio(
        "ラベル表示",
        options=list(_ANNOTATION_OPTIONS.keys()),
        index=1,  # default = extremes(上位5+下位5)
        horizontal=True,
        key=f"annotation_{indicator_id}_{horizon}",
    )
    annotation_mode: AnnotationMode = _ANNOTATION_OPTIONS[chosen_label]

    pack = values_for(indicator_id, horizon)
    values = pack.values
    num_with_value = sum(1 for v in values.values() if v is not None)
    num_no_pred = 47 - num_with_value

    fig = render_choropleth(
        values,
        indicator_label=f"{indicator_label}({horizon_label})",
        annotation_mode=annotation_mode,
    )
    st.plotly_chart(fig, use_container_width=True)

    # データ鮮度・取得元の透明性
    if pack.availability.source == "db":
        if pack.availability.last_updated:
            ts = pack.availability.last_updated.strftime("%Y-%m-%d %H:%M")
            st.caption(f"🔵 DB 実データ表示中 / 最終更新: {ts}")
        else:
            st.caption("🔵 DB 実データ表示中")
    else:
        note = pack.availability.note or "DB 未準備"
        st.caption(f"🟡 ダミーデータ表示中({note})")

    if num_no_pred > 0:
        st.caption(f"⚠️ 予測対象外の都道府県: {num_no_pred}/47(灰色表示)")
