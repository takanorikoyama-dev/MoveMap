"""2 県比較タブ: 都道府県を 2 つ選んで 7 指標の偏差値をレーダーチャートで横並び表示."""

from __future__ import annotations

from typing import Literal

import plotly.graph_objects as go
import streamlit as st

from app.features.map_view.ranking import ALL_INDICATORS, compute_ranking, stars_to_unicode
from app.features.map_view.regions import region_of
from app.features.map_view.usecases.switch_indicator import (
    INDICATOR_ICONS,
    INDICATOR_LABELS,
    INDICATOR_UNITS,
)

Horizon = Literal["current", "3y", "5y", "10y"]


def show_comparison(horizon: Horizon = "current") -> None:
    """2 県を選んでレーダーチャート + 数値テーブルで比較."""
    st.subheader("2 県を比較する")
    st.caption(
        "7 指標を住みやすさ偏差値(50=平均、>50=平均より良い)に揃えて、レーダーチャートで重ねます。"
        " 値が外側に広いほど住みやすい。"
    )

    ranks = compute_ranking(horizon=horizon)
    options = {f"{r.prefecture_code} {r.prefecture_name}": r for r in ranks}
    labels = list(options.keys())

    c1, c2 = st.columns(2)
    with c1:
        a_label = st.selectbox(
            "県 A",
            options=labels,
            index=labels.index("13 東京都") if "13 東京都" in labels else 0,
            key=f"compare_a_{horizon}",
        )
    with c2:
        b_label = st.selectbox(
            "県 B",
            options=labels,
            index=labels.index("40 福岡県") if "40 福岡県" in labels else 1,
            key=f"compare_b_{horizon}",
        )

    a, b = options[a_label], options[b_label]

    # レーダーチャート(偏差値 30〜70 を半径に)
    categories = [
        f"{INDICATOR_ICONS.get(ind, '')} {INDICATOR_LABELS[ind]}"  # type: ignore[index,arg-type]
        for ind in ALL_INDICATORS
    ]
    a_scores = [a.per_indicator_score[ind] or 50.0 for ind in ALL_INDICATORS]
    b_scores = [b.per_indicator_score[ind] or 50.0 for ind in ALL_INDICATORS]

    fig = go.Figure()
    fig.add_trace(
        go.Scatterpolar(
            r=a_scores + [a_scores[0]],
            theta=categories + [categories[0]],
            fill="toself",
            name=f"{a.prefecture_code} {a.prefecture_name}",
            line={"color": "#3b82f6", "width": 2},
            fillcolor="rgba(59,130,246,0.25)",
        )
    )
    fig.add_trace(
        go.Scatterpolar(
            r=b_scores + [b_scores[0]],
            theta=categories + [categories[0]],
            fill="toself",
            name=f"{b.prefecture_code} {b.prefecture_name}",
            line={"color": "#ef4444", "width": 2},
            fillcolor="rgba(239,68,68,0.25)",
        )
    )
    fig.update_layout(
        polar={
            "radialaxis": {
                "visible": True,
                "range": [25, 75],
                "tickvals": [30, 40, 50, 60, 70],
                "tickfont": {"size": 10},
            },
            "angularaxis": {"tickfont": {"size": 12}},
        },
        showlegend=True,
        height=520,
        margin={"t": 40, "b": 40, "l": 60, "r": 60},
        title={"text": "<b>住みやすさ偏差値プロファイル比較</b>", "x": 0.5},
    )
    st.plotly_chart(fig, use_container_width=True)

    # 数値テーブル
    rows = []
    for ind in ALL_INDICATORS:
        a_val = a.per_indicator_value[ind]
        b_val = b.per_indicator_value[ind]
        a_sc = a.per_indicator_score[ind]
        b_sc = b.per_indicator_score[ind]
        diff = None if (a_sc is None or b_sc is None) else round(a_sc - b_sc, 1)
        winner = "A" if (diff is not None and diff > 0) else "B" if (diff is not None and diff < 0) else "—"
        rows.append({
            "指標": f"{INDICATOR_ICONS.get(ind, '')} {INDICATOR_LABELS[ind]} {INDICATOR_UNITS.get(ind, '')}",  # type: ignore[index,arg-type]
            "A 実数値": a_val,
            "A 偏差値": round(a_sc, 1) if a_sc is not None else None,
            "B 実数値": b_val,
            "B 偏差値": round(b_sc, 1) if b_sc is not None else None,
            "A−B 偏差値差": diff,
            "勝者": winner,
        })

    import pandas as pd

    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True, hide_index=True)

    # サマリ
    a_better = sum(1 for r in rows if r["勝者"] == "A")
    b_better = sum(1 for r in rows if r["勝者"] == "B")
    cols = st.columns(2)
    with cols[0]:
        st.metric(
            f"{a.prefecture_code} {a.prefecture_name}({region_of(a.prefecture_code)})",
            stars_to_unicode(a.stars),
            f"総合 {a.composite_score:.1f} / 7指標中 {a_better} 勝" if a.composite_score else "—",
        )
    with cols[1]:
        st.metric(
            f"{b.prefecture_code} {b.prefecture_name}({region_of(b.prefecture_code)})",
            stars_to_unicode(b.stars),
            f"総合 {b.composite_score:.1f} / 7指標中 {b_better} 勝" if b.composite_score else "—",
        )


__all__ = ["show_comparison"]
