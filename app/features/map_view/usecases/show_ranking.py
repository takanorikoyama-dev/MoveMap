"""ランキングタブ表示 Usecase.

47 都道府県 × 7 指標(実数値) + 総合偏差値 + 星 を DataFrame で表示.

UI/UX 機能(2026-05-19 拡充):
    - 各指標列は **実数値** を表示(列見出しに ↑/↓ + 単位)
    - セル背景色は偏差値ベース(緑=良い〜赤=悪い)
    - 順位は 🥇🥈🥉 メダル + 番号
    - マイクロチャート(プログレスバー)で偏差値を視覚化
    - 地方フィルタ・しきい値フィルタ(総合偏差値・★)
    - 7 指標の重み付けスライダー(ユーザーの優先度反映)
    - お気に入りピン留め(複数県を上に固定)
    - CSV エクスポート + URL 共有(query_params)
    - 表形式 / カード形式 切替
"""

from __future__ import annotations

from typing import Literal

import pandas as pd
import streamlit as st

from app.features.map_view._cache import cached_ranking
from app.features.map_view.images import credit_line, get_thumb
from app.features.map_view.ranking import (
    ALL_INDICATORS,
    HIGHER_IS_BETTER,
    LOWER_IS_BETTER,
    stars_to_unicode,
)
from app.features.map_view.regions import medal_for_rank, region_of
from app.features.map_view.usecases.switch_indicator import (
    INDICATOR_DEFINITIONS,
    INDICATOR_ICONS,
    INDICATOR_LABELS,
    INDICATOR_UNITS,
)

# 列値の表示スケール(指標 → 表示倍率, 表示書式).
_DISPLAY_SCALE: dict[str, tuple[float, str]] = {
    "land_price": (1 / 10_000.0, "{:.1f}"),
    "rent_index": (1 / 10_000.0, "{:.1f}"),
    "birth_count": (1 / 10_000.0, "{:.1f}"),
    "price_index": (1.0, "{:.1f}"),
    "air_quality": (1.0, "{:.0f}"),
    "disaster_risk": (1.0, "{:.2f}"),
    "transport_access": (1.0, "{:.2f}"),
    "public_safety": (1.0, "{:.1f}"),     # 件/千人(正規化済、整数倍なしの 1 桁小数)
    "net_migration": (1.0, "{:.2f}"),     # ‰
}

Horizon = Literal["current", "3y", "5y", "10y"]


def _direction_arrow(indicator_id: str) -> str:
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
    if score is None or pd.isna(score):
        return "background-color: #f0f0f0; color: #999;"
    s = max(30.0, min(70.0, float(score)))
    if s >= 50.0:
        t = (s - 50.0) / 20.0
        r = int(255 - 135 * t)
        g = int(255 - 55 * t)
        b = int(255 - 135 * t)
    else:
        t = (50.0 - s) / 20.0
        r = int(255 - 25 * t)
        g = int(255 - 115 * t)
        b = int(255 - 115 * t)
    return f"background-color: rgb({r},{g},{b}); color: #000;"


def _column_header(indicator_id: str) -> str:
    icon = INDICATOR_ICONS.get(indicator_id, "")  # type: ignore[arg-type]
    label = INDICATOR_LABELS.get(indicator_id, indicator_id)  # type: ignore[arg-type]
    arrow = _direction_arrow(indicator_id)
    unit = INDICATOR_UNITS.get(indicator_id, "")  # type: ignore[arg-type]
    return f"{icon} {label} {arrow} {unit}".strip()


def _make_formatter(fmt: str):
    def _fmt(v: object) -> str:
        if v is None or (isinstance(v, float) and pd.isna(v)):
            return "—"
        try:
            return fmt.format(float(v))
        except (TypeError, ValueError):
            return str(v)

    return _fmt


def _render_weight_sliders(horizon: Horizon) -> dict[str, float]:
    """7 指標の重み付けスライダー(0-100)."""
    with st.expander("⚖️ あなたの優先度で重み付け(0=無視、100=最重視)", expanded=False):
        st.caption("各指標のスライダーを動かすと、総合偏差値が即座に再計算されます(0 にすればその指標を除外)。")
        weights: dict[str, float] = {}
        cols = st.columns(4)
        for i, ind in enumerate(ALL_INDICATORS):
            with cols[i % 4]:
                # key を horizon 非依存に統一(キャッシュヒット率向上 + horizon 切替時の重み維持)
                weights[ind] = st.slider(
                    f"{INDICATOR_ICONS.get(ind, '')} {INDICATOR_LABELS[ind]}",
                    min_value=0,
                    max_value=100,
                    value=st.session_state.get(f"weight_{ind}", 50),
                    step=10,
                    key=f"weight_{ind}",
                )
        cb = st.columns([1, 1, 6])
        with cb[0]:
            if st.button("均等にリセット", key="reset_weight"):
                for ind in ALL_INDICATORS:
                    st.session_state[f"weight_{ind}"] = 50
                st.rerun()
    return weights


def _render_pin_selector(horizon: Horizon, pref_codes_and_names: list[tuple[str, str]]) -> list[str]:
    """お気に入りピン留め(複数選択 → 上に固定)."""
    options = [f"{c} {n}" for c, n in pref_codes_and_names]
    pinned_labels = st.multiselect(
        "📌 お気に入りピン留め(上に固定表示)",
        options=options,
        default=st.session_state.get(f"pinned_{horizon}", []),
        key=f"pinned_{horizon}",
    )
    return [s.split(" ", 1)[0] for s in pinned_labels]


def show_ranking(horizon: Horizon = "current") -> None:
    """ランキング画面を描画."""
    st.subheader("都道府県ランキング(住みやすさ総合)")
    st.caption(
        "**住みやすさスコア(=総合偏差値)** で並べた都道府県ランキングです。"
        f"対象時点: **{horizon}** ｜ "
        "50 が全国平均、60 以上で「平均より良い」、70 以上で「全国トップクラス」の目安です。"
        " 各観点はあなたの優先度(⚖️ スライダー)で重み付けできます。"
        " セルの色: 🟢 平均より良い 〜 🔴 平均より悪い。"
    )

    # --- コントロール ---
    weights = _render_weight_sliders(horizon)

    # --- ランキング計算(キャッシュ付き、重み反映) ---
    ranks = cached_ranking(horizon=horizon, weights=weights)
    pref_codes_and_names = [(r.prefecture_code, r.prefecture_name) for r in ranks]

    # --- DataFrame 構築 ---
    rows_value: list[dict[str, object]] = []
    rows_score: list[dict[str, object]] = []
    for r in ranks:
        row_v: dict[str, object] = {
            "順位": "—",
            "★": stars_to_unicode(r.stars),
            "総合偏差値": r.composite_score,
            "都道府県": f"{r.prefecture_code} {r.prefecture_name}",
            "地方": region_of(r.prefecture_code),
            "_code": r.prefecture_code,
        }
        row_s: dict[str, object] = {
            "順位": None, "★": None, "総合偏差値": r.composite_score,
            "都道府県": None, "地方": None, "_code": r.prefecture_code,
        }
        for ind in ALL_INDICATORS:
            col = _column_header(ind)
            raw_value = r.per_indicator_value[ind]
            scale, _ = _DISPLAY_SCALE.get(ind, (1.0, "{:.1f}"))
            row_v[col] = None if raw_value is None else raw_value * scale
            row_s[col] = r.per_indicator_score[ind]
        rows_value.append(row_v)
        rows_score.append(row_s)

    df_value = pd.DataFrame(rows_value)
    df_score = pd.DataFrame(rows_score)

    # 並べ替え + 順位
    sort_idx = df_value.sort_values("総合偏差値", ascending=False, na_position="last").index
    df_value = df_value.loc[sort_idx].reset_index(drop=True)
    df_score = df_score.loc[sort_idx].reset_index(drop=True)
    df_value["_rank_int"] = [
        i + 1 if pd.notna(score) else None for i, score in enumerate(df_value["総合偏差値"])
    ]
    df_value["順位"] = [
        medal_for_rank(int(r)) if pd.notna(r) else "—" for r in df_value["_rank_int"]
    ]
    df_value["総合偏差値"] = df_value["総合偏差値"].round(1)

    # ピン留め(上に並べる)
    pinned_codes = _render_pin_selector(horizon, pref_codes_and_names)

    df_filtered = df_value.copy()
    df_score_filtered = df_score.copy()

    # ピン留めを上に
    if pinned_codes:
        pin_mask = df_filtered["_code"].isin(pinned_codes)
        df_filtered = pd.concat(
            [df_filtered[pin_mask], df_filtered[~pin_mask]]
        ).reset_index(drop=True)
        df_score_filtered = pd.concat(
            [df_score_filtered[pin_mask.values], df_score_filtered[~pin_mask.values]]
        ).reset_index(drop=True)
        df_filtered["順位"] = df_filtered.apply(
            lambda row: f"📌 {row['順位']}" if row["_code"] in pinned_codes else row["順位"],
            axis=1,
        )

    n = len(df_filtered)
    st.caption(f"全 **{n} 県** を住みやすさスコア順で表示中")

    # --- Top 3 ハイライト(画像付き、Apple カード風)---
    _render_top3_hero(df_filtered)

    # --- 表示モード切替 ---
    view_mode = st.radio(
        "表示モード",
        options=["📊 表(マイクロチャート付き)", "🪪 カード形式"],
        index=0,
        horizontal=True,
        key=f"view_mode_{horizon}",
    )

    if view_mode.startswith("📊"):
        _render_table_view(df_filtered, df_score_filtered)
    else:
        _render_card_view(df_filtered, df_score_filtered)

    # サマリ + ダウンロード
    st.markdown("---")
    csv_bytes = df_filtered.drop(columns=["_code", "_rank_int"], errors="ignore").to_csv(
        index=False
    ).encode("utf-8-sig")
    cdl, csum = st.columns([1.2, 3])
    with cdl:
        st.download_button(
            "📥 CSV ダウンロード",
            data=csv_bytes,
            file_name=f"movemap_ranking_{horizon}.csv",
            mime="text/csv",
        )
    with csum:
        top = df_filtered.head(3)
        bottom = df_filtered.tail(3)
        st.markdown("**上位 3:** " + " / ".join(
            f"{row['順位']} {row['★']} {row['都道府県']}({row['総合偏差値']})"
            for _, row in top.iterrows()
        ))
        if len(df_filtered) >= 6:
            st.markdown("**下位 3:** " + " / ".join(
                f"{row['★']} {row['都道府県']}({row['総合偏差値']})"
                for _, row in bottom.iterrows()
            ))


def _render_top3_hero(df: pd.DataFrame) -> None:
    """ランキング上位 3 県をヒーロー画像付きで横並びに表示."""
    top3 = df.head(3)
    if top3.empty:
        return

    st.markdown("### 🏆 住みやすさトップ 3")
    cols = st.columns(3, gap="medium")
    for i, (_, row) in enumerate(top3.iterrows()):
        with cols[i]:
            code = str(row.get("_code", ""))
            thumb = get_thumb(code)
            if thumb:
                st.image(thumb.url, use_container_width=True)
                st.caption(credit_line(thumb))
            rank_text = str(row.get("順位") or "")
            stars = str(row.get("★") or "")
            pref = str(row.get("都道府県") or "")
            score = row.get("総合偏差値")
            score_text = (
                f"{score:.1f}" if isinstance(score, (int, float)) else "—"
            )
            st.markdown(
                f"#### {rank_text} {pref}"
            )
            st.markdown(
                f"{stars} ｜ 住みやすさスコア **{score_text}**"
            )
    st.markdown("---")


def _render_table_view(df_value: pd.DataFrame, df_score: pd.DataFrame) -> None:
    """表モード: Styler で色付け + マイクロチャート(プログレスバー)."""
    indicator_columns = [_column_header(ind) for ind in ALL_INDICATORS]
    df_view = df_value.drop(columns=["_code", "_rank_int"], errors="ignore").copy()

    # column_config: 各指標列を ProgressColumn にしたいところだが、ProgressColumn は
    # 単一スケールで描画されるため指標ごとに範囲が違うと比較不能.
    # → Styler.bar(背景の棒)を偏差値ベースで重ねる(色付けと両立)
    styler = df_view.style

    # 偏差値ベースでセル背景色(緑〜赤)
    for col in indicator_columns:
        styler = styler.apply(
            lambda s, c=col: [_score_to_color(score) for score in df_score[c]],
            subset=[col],
        )
    styler = styler.apply(
        lambda s: [_score_to_color(score) for score in df_value["総合偏差値"]],
        subset=["総合偏差値"],
    )

    # 総合偏差値列にマイクロバー(値そのものを bar の長さに)
    styler = styler.bar(
        subset=["総合偏差値"], color="#a0d8c5", vmin=30.0, vmax=70.0, align="zero",
    )

    # フォーマット
    fmt_map: dict[str, object] = {"総合偏差値": "{:.1f}"}
    for ind in ALL_INDICATORS:
        col = _column_header(ind)
        _, fmt = _DISPLAY_SCALE.get(ind, (1.0, "{:.1f}"))
        fmt_map[col] = _make_formatter(fmt)
    styler = styler.format(fmt_map)

    column_config: dict[str, object] = {
        "順位": st.column_config.TextColumn("順位", width="small"),
        "★": st.column_config.TextColumn("★ 評価", width="small"),
        "総合偏差値": st.column_config.NumberColumn(
            "総合偏差値",
            help="7 指標を住みやすさ方向で揃えて偏差値化、(重み付け)平均",
            width="small",
        ),
        "都道府県": st.column_config.TextColumn("都道府県", width="medium"),
        "地方": st.column_config.TextColumn("地方", width="small"),
    }
    for ind in ALL_INDICATORS:
        col = _column_header(ind)
        d = INDICATOR_DEFINITIONS.get(ind, {})  # type: ignore[arg-type]
        tip = (
            f"{INDICATOR_LABELS[ind]} {INDICATOR_UNITS[ind]}\n"  # type: ignore[index]
            f"{d.get('what','')}\n{_direction_help(ind)}\n"
            f"出典: {d.get('source','')}"
        )
        column_config[col] = st.column_config.NumberColumn(col, help=tip)

    st.dataframe(
        styler,
        use_container_width=True,
        hide_index=True,
        column_config=column_config,
        height=min(900, 40 * (len(df_view) + 1) + 40),
    )


def _render_card_view(df_value: pd.DataFrame, df_score: pd.DataFrame) -> None:
    """カードモード: 各都道府県を縦並びのカードで表示."""
    indicator_columns = [_column_header(ind) for ind in ALL_INDICATORS]
    for i, (_, row) in enumerate(df_value.iterrows()):
        with st.container(border=True):
            c1, c2 = st.columns([1, 4])
            with c1:
                st.markdown(f"### {row['順位']}")
                st.markdown(f"#### {row['★']}")
            with c2:
                st.markdown(f"**{row['都道府県']}** _{row['地方']}_")
                comp = row["総合偏差値"]
                st.markdown(f"総合偏差値: **{comp}**" if pd.notna(comp) else "総合偏差値: —")
                # 各指標を 1 行で
                lines = []
                for ind in ALL_INDICATORS:
                    col = _column_header(ind)
                    v = row.get(col)
                    s = df_score.loc[i, col] if i in df_score.index else None
                    _, fmt = _DISPLAY_SCALE.get(ind, (1.0, "{:.1f}"))
                    vtxt = "—" if pd.isna(v) else fmt.format(float(v))
                    badge = f"({float(s):.0f})" if isinstance(s, (int, float)) and not pd.isna(s) else ""
                    lines.append(f"{INDICATOR_LABELS[ind]} {_direction_arrow(ind)}: **{vtxt}** {badge}")
                st.markdown(" / ".join(lines))


__all__ = ["show_ranking"]
