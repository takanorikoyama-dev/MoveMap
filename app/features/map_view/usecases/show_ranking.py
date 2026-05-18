"""ランキングタブ表示 Usecase.

47 都道府県 × 7 指標(実数値) + 総合偏差値 + 星 を DataFrame で表示.
- 各指標列は **実数値** を表示(列見出しに ↑/↓ で住みやすさ方向を明示).
- セル背景色は偏差値ベース(緑=良い〜赤=悪い)で良し悪しを可視化.
- 列クリックでソート可能(Streamlit デフォルト機能).
"""

from __future__ import annotations

from typing import Literal

import pandas as pd
import streamlit as st

from app.features.map_view.ranking import (
    ALL_INDICATORS,
    HIGHER_IS_BETTER,
    LOWER_IS_BETTER,
    compute_ranking,
    stars_to_unicode,
)
from app.features.map_view.usecases.switch_indicator import INDICATOR_LABELS

Horizon = Literal["current", "3y", "5y", "10y"]


def _direction_arrow(indicator_id: str) -> str:
    """住みやすさ方向の矢印(列見出し用)."""
    if indicator_id in HIGHER_IS_BETTER:
        return "↑"
    if indicator_id in LOWER_IS_BETTER:
        return "↓"
    return ""


def _direction_help(indicator_id: str) -> str:
    if indicator_id in HIGHER_IS_BETTER:
        return "↑ 高いほど良い"
    if indicator_id in LOWER_IS_BETTER:
        return "↓ 低いほど良い"
    return "—"


def _score_to_color(score: float | None) -> str:
    """偏差値 → セル背景色(緑=良い、赤=悪い、グレー=データなし)."""
    if score is None or pd.isna(score):
        return "background-color: #f0f0f0; color: #999;"
    # 30〜70 を緑〜赤のグラデーションに線形マッピング
    s = max(30.0, min(70.0, float(score)))
    # 50 を中立(薄い黄)、>50 緑系、<50 赤系
    if s >= 50.0:
        # 50→白(255,255,255), 70→緑(120,200,120)
        t = (s - 50.0) / 20.0
        r = int(255 - 135 * t)
        g = int(255 - 55 * t)
        b = int(255 - 135 * t)
    else:
        # 50→白(255,255,255), 30→赤(230,140,140)
        t = (50.0 - s) / 20.0
        r = int(255 - 25 * t)
        g = int(255 - 115 * t)
        b = int(255 - 115 * t)
    return f"background-color: rgb({r},{g},{b}); color: #000;"


def show_ranking(horizon: Horizon = "current") -> None:
    """ランキング画面を描画."""
    st.subheader("都道府県ランキング(住みやすさ総合)")

    st.caption(
        f"対象時点: **{horizon}** ｜ "
        "各指標を 50±Z×10 で偏差値化し、住みやすさ方向(↑↓)を反映した上で 7 指標を等加重平均しています。"
        " セルの色は偏差値ベース(🟢良い〜🔴悪い)です。"
    )

    ranks = compute_ranking(horizon=horizon)

    # --- 表示用 DataFrame: 実数値ベース ---
    rows_value: list[dict[str, object]] = []
    rows_score: list[dict[str, object]] = []
    for r in ranks:
        row_v: dict[str, object] = {
            "順位": "—",
            "★": stars_to_unicode(r.stars),
            "総合偏差値": r.composite_score,
            "都道府県": f"{r.prefecture_code} {r.prefecture_name}",
        }
        row_s: dict[str, object] = {
            "順位": None,
            "★": None,
            "総合偏差値": r.composite_score,
            "都道府県": None,
        }
        for ind in ALL_INDICATORS:
            col = f"{INDICATOR_LABELS[ind]} {_direction_arrow(ind)}"
            row_v[col] = r.per_indicator_value[ind]    # 実数値表示
            row_s[col] = r.per_indicator_score[ind]    # 色付け用(偏差値)
        rows_value.append(row_v)
        rows_score.append(row_s)

    df_value = pd.DataFrame(rows_value)
    df_score = pd.DataFrame(rows_score)

    # 総合偏差値降順で並べ替え + 順位付与
    sort_idx = df_value.sort_values("総合偏差値", ascending=False, na_position="last").index
    df_value = df_value.loc[sort_idx].reset_index(drop=True)
    df_score = df_score.loc[sort_idx].reset_index(drop=True)
    df_value["順位"] = [
        (i + 1 if pd.notna(score) else "—")
        for i, score in enumerate(df_value["総合偏差値"])
    ]

    # 総合偏差値の小数桁数調整
    df_value["総合偏差値"] = df_value["総合偏差値"].round(1)

    # --- 色付け Styler ---
    indicator_columns = [f"{INDICATOR_LABELS[ind]} {_direction_arrow(ind)}" for ind in ALL_INDICATORS]

    def _style_indicator_cell(_val: object, score: float | None) -> str:
        return _score_to_color(score)

    styler = df_value.style
    # 各指標列を、対応する偏差値(df_score の同名列)で着色
    for col in indicator_columns:
        styler = styler.apply(
            lambda s, c=col: [_score_to_color(score) for score in df_score[c]],
            subset=[col],
        )
    # 総合偏差値列も同じ規則で着色
    styler = styler.apply(
        lambda s: [_score_to_color(score) for score in df_value["総合偏差値"]],
        subset=["総合偏差値"],
    )
    # 数値フォーマット(列ごとに桁数を変える可能性に備え一括 %.2f → 後で必要なら個別調整)
    styler = styler.format({col: _fmt_number for col in indicator_columns})
    styler = styler.format({"総合偏差値": "{:.1f}"})

    # column_config(ヘルプ tooltip 用)
    column_config: dict[str, object] = {
        "順位": st.column_config.TextColumn("順位", width="small"),
        "★": st.column_config.TextColumn("★ 評価", width="small"),
        "総合偏差値": st.column_config.NumberColumn(
            "総合偏差値",
            help="7 指標を住みやすさ方向で揃えて偏差値化、等加重平均(30〜70 でセル色変化)",
            width="small",
        ),
        "都道府県": st.column_config.TextColumn("都道府県", width="medium"),
    }
    for ind in ALL_INDICATORS:
        col = f"{INDICATOR_LABELS[ind]} {_direction_arrow(ind)}"
        column_config[col] = st.column_config.NumberColumn(
            col,
            help=f"{INDICATOR_LABELS[ind]} ({_direction_help(ind)})。セル色は住みやすさ偏差値ベース。",
        )

    st.dataframe(
        styler,
        use_container_width=True,
        hide_index=True,
        column_config=column_config,
        height=min(820, 40 * (len(df_value) + 1) + 40),
    )

    # サマリ
    top = df_value.head(5)
    bottom = df_value.tail(5)
    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown("**上位 5 都道府県(住みやすさ高)**")
        for _, row in top.iterrows():
            st.markdown(f"- {row['★']} {row['都道府県']} ({row['総合偏差値']})")
    with col_b:
        st.markdown("**下位 5 都道府県**")
        for _, row in bottom.iterrows():
            st.markdown(f"- {row['★']} {row['都道府県']} ({row['総合偏差値']})")

    st.caption(
        "※ ↑↓ は「住みやすさ」観点での方向。"
        "例えば物価指数は **低い方が良い(住みやすい)** として扱います。"
        "観点を変える場合は将来のカスタム重み付け機能で対応予定(Should 段階)。"
    )


def _fmt_number(v: object) -> str:
    """指標実数値の表示用フォーマッタ(None → '—'、整数値 → 整数、小数 → 1桁)."""
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return "—"
    try:
        fv = float(v)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return str(v)
    if abs(fv - round(fv)) < 1e-9 and abs(fv) < 1e9:
        return f"{int(round(fv)):,}"
    return f"{fv:,.1f}"


__all__ = ["show_ranking"]
