"""SF-001 ShowMap — 47都道府県の選択中指標・年次でヒートマップ描画.

参照: outputs/06_system_design/05_画面設計.md (SCR-001)
データ源: app.features.map_view.data_provider 経由(DB → dummy フォールバック)

UI/UX 強化(2026-05-19):
    - カラースケール RdYlGn + direction 反映で「緑=住みやすい」統一
    - 上位3に金/銀/銅メダル
    - ツールチップに県名+値+総合偏差値+順位+★
    - 地域ジャンプ・主要都市マーカートグル
"""

from __future__ import annotations

from typing import Literal

import streamlit as st

from app.features.map_view._cache import cached_ranking, cached_values_for
from app.features.map_view.components.heatmap import AnnotationMode, render_choropleth
from app.features.map_view.ranking import (
    HIGHER_IS_BETTER,
    LOWER_IS_BETTER,
    stars_to_unicode,
)
from app.features.map_view.regions import REGION_BOUNDS, medal_for_rank
from app.features.map_view.usecases.switch_horizon import HORIZON_LABELS
from app.features.map_view.usecases.switch_indicator import (
    INDICATOR_DEFINITIONS,
    INDICATOR_ICONS,
    INDICATOR_LABELS,
    INDICATOR_UNITS,
    IndicatorId,
)

Horizon = Literal["current", "3y", "5y", "10y"]

_ANNOTATION_OPTIONS: dict[str, AnnotationMode] = {
    "OFF(地図のみ)": "off",
    "上位5+下位5 を引き出し線で表示": "extremes",
    "47都道府県すべて表示": "all",
}


def _build_rich_hover(
    indicator_id: IndicatorId,
    horizon: Horizon,
    values: dict[str, float | None],
) -> dict[str, dict[str, object]]:
    """choropleth の customdata に渡す追加情報(総合偏差値・順位・★)を構築."""
    ranks = cached_ranking(horizon=horizon)
    info: dict[str, dict[str, object]] = {}
    # 当該指標の値で並べた順位(住みやすさ方向)
    higher = indicator_id in HIGHER_IS_BETTER
    indicator_ranking = sorted(
        ((c, v) for c, v in values.items() if v is not None),
        key=lambda kv: kv[1],
        reverse=higher,
    )
    indicator_rank_map = {code: i + 1 for i, (code, _) in enumerate(indicator_ranking)}
    unit = INDICATOR_UNITS.get(indicator_id, "")
    for r in ranks:
        ind_rank = indicator_rank_map.get(r.prefecture_code)
        info[r.prefecture_code] = {
            "name": r.prefecture_name,
            "value_unit": "",  # 単位は kosher format でテンプレ外に表示
            "rank": medal_for_rank(ind_rank) if ind_rank else "—",
            "composite": f"{r.composite_score:.1f}" if r.composite_score is not None else "—",
            "stars": stars_to_unicode(r.stars),
        }
        _ = unit
    return info


def show_map(indicator_id: IndicatorId, horizon: Horizon) -> None:
    """選択中の指標・年次で MAP を描画する.

    Args:
        indicator_id: 表示する指標 ID.
        horizon: 現在 or 予測時点.
    """
    indicator_label = f"{INDICATOR_ICONS.get(indicator_id, '')} {INDICATOR_LABELS[indicator_id]}".strip()
    horizon_label = HORIZON_LABELS[horizon]
    is_lower_better = indicator_id in LOWER_IS_BETTER

    # コントロールを 3 列に並べる(ラベル / 地域 / 主要都市)
    c1, c2, c3 = st.columns([2.2, 1.6, 1.2])
    with c1:
        chosen_label = st.radio(
            "ラベル表示",
            options=list(_ANNOTATION_OPTIONS.keys()),
            index=1,
            horizontal=True,
            key=f"annotation_{indicator_id}_{horizon}",
        )
    with c2:
        chosen_region = st.selectbox(
            "地域ジャンプ",
            options=list(REGION_BOUNDS.keys()),
            index=0,
            key=f"region_zoom_{indicator_id}_{horizon}",
        )
    with c3:
        show_cities = st.checkbox(
            "主要都市マーカー",
            value=True,
            key=f"major_cities_{indicator_id}_{horizon}",
        )
    annotation_mode: AnnotationMode = _ANNOTATION_OPTIONS[chosen_label]

    pack = cached_values_for(indicator_id, horizon)
    values = pack.values
    num_with_value = sum(1 for v in values.values() if v is not None)
    num_no_pred = 47 - num_with_value

    rich_hover = _build_rich_hover(indicator_id, horizon, values)

    fig = render_choropleth(
        values,
        indicator_label=f"{indicator_label}({horizon_label}) {INDICATOR_UNITS.get(indicator_id, '')}",
        annotation_mode=annotation_mode,
        reverse_color=is_lower_better,  # 低い方が良い指標は色を反転して 緑=住みやすい に統一
        show_major_cities=show_cities,
        region_zoom=chosen_region,
        rich_hover=rich_hover,
    )
    st.plotly_chart(fig, use_container_width=True)

    # 指標の意味を地図直下にも(地図を最初に見る人向け)
    d = INDICATOR_DEFINITIONS.get(indicator_id, {})
    if d:
        st.caption(f"💡 {d.get('what', '')} / {d.get('interpret', '')}")

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
