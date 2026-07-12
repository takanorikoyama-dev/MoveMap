"""SF-001 ShowMap — 47都道府県の選択中指標・年次でヒートマップ描画.

参照: outputs/06_system_design/05_画面設計.md (SCR-001)
データ源: app.features.map_view.data_provider 経由(DB → dummy フォールバック)

UI/UX 強化(2026-05-19):
    - カラースケール RdYlGn + direction 反映で「緑=住みやすい」統一
    - 上位3に金/銀/銅メダル
    - ツールチップに県名+値+総合偏差値+順位+★
    - 地域ジャンプ・主要都市マーカートグル

UI/UX 再設計(2026-07-12、案 A + ①):
    背景: Map 画面は「単一指標しか見られない」「値が読める県が上位/下位10県のみ」
    「コントロール過多で認知負荷が高い」「地図固有の空間性(地理的まとまり)を
    活用できていない」という構造的課題があった(Ranking表の劣化版になっていた).
    対応:
        - ラベル表示のデフォルトを「47都道府県すべて表示」に変更(見れば分かる)
        - コントロールを「主要(ラベル・地域ジャンプ)」+「詳細設定(expander に
          畳む: 主要都市・非日常スポット・県絞り込み)」の2階層に整理
        - 地方別平均サマリー(8ブロック)を新設。地理的クラスタ傾向を一目で
          把握できるようにし、Map 固有のジョブ(空間的パターン認識)を担保
"""

from __future__ import annotations

import statistics
from typing import Literal

import streamlit as st

from app.features.map_view._cache import cached_ranking, cached_values_for
from app.features.map_view.components.heatmap import AnnotationMode, render_choropleth
from app.features.map_view.osm import (
    CATEGORY_LABELS,
    POI,
    fetch_pois,
    get_prefecture_bbox,
)
from app.features.map_view.ranking import (
    HIGHER_IS_BETTER,
    LOWER_IS_BETTER,
    stars_to_unicode,
)
from app.features.map_view.regions import (
    PREFECTURE_REGIONS,
    REGION_BOUNDS,
    REGIONS,
    medal_for_rank,
)
from app.features.map_view.usecases.show_prefecture_detail import PREFECTURE_NAMES
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

# 非日常スポットのカテゴリチェックボックス順序
_SPOT_CATEGORY_ORDER: tuple[str, ...] = (
    "shrine_temple", "castle", "onsen", "viewpoint", "museum", "park", "waterfall", "attraction",
)


@st.cache_data(ttl=3600, show_spinner=False)
def _cached_pois(pref_code: str, categories_key: tuple[str, ...]) -> list[POI]:
    """OSM Overpass を 1 時間キャッシュ."""
    bbox = get_prefecture_bbox(pref_code)
    if not bbox:
        return []
    return fetch_pois(bbox, list(categories_key), limit=40)


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


def _render_region_summary(values: dict[str, float | None], reverse_color: bool) -> None:
    """8 地方ブロックの平均値を横並びで表示(地理的クラスタ傾向を一目で把握、2026-07-12).

    Map 画面固有のジョブ(Ranking 表では代替できない空間的パターン認識)を
    担保するための最小実装. 「どの地方(隣接県のまとまり)が良い/悪い傾向か」を
    47 県ぶんの個別データを追わずに把握できる.
    """
    region_values: dict[str, list[float]] = {r: [] for r in REGIONS}
    for code, val in values.items():
        if val is None:
            continue
        region = PREFECTURE_REGIONS.get(code)
        if region:
            region_values[region].append(val)

    region_avg = {r: statistics.mean(vs) for r, vs in region_values.items() if vs}
    if not region_avg:
        return

    # 住みやすさ方向で並べ替え(reverse_color=True なら値が低いほど住みやすい)
    sorted_regions = sorted(region_avg.items(), key=lambda kv: kv[1], reverse=not reverse_color)

    st.markdown("**🗾 地方別の傾向**(平均値・住みやすい順 — 地理的なまとまりを一目で)")
    cols = st.columns(len(sorted_regions))
    for i, (region, avg) in enumerate(sorted_regions):
        with cols[i]:
            medal = medal_for_rank(i + 1) if i < 3 else ""
            st.metric(f"{medal} {region}".strip(), f"{avg:.1f}")


def show_map(indicator_id: IndicatorId, horizon: Horizon) -> None:
    """選択中の指標・年次で MAP を描画する.

    Args:
        indicator_id: 表示する指標 ID.
        horizon: 現在 or 予測時点.
    """
    indicator_label = f"{INDICATOR_ICONS.get(indicator_id, '')} {INDICATOR_LABELS[indicator_id]}".strip()
    horizon_label = HORIZON_LABELS[horizon]
    is_lower_better = indicator_id in LOWER_IS_BETTER

    # --- 主要コントロール(常時表示): ラベル表示 + 地域ジャンプ ---
    # 2026-07-12: 「見れば分かる」を実現するため、デフォルトを
    # 「47都道府県すべて表示」に変更(以前は上位/下位10県のみ表示だった).
    c1, c2 = st.columns([2.4, 1.6])
    with c1:
        chosen_label = st.radio(
            "ラベル表示",
            options=list(_ANNOTATION_OPTIONS.keys()),
            index=2,
            horizontal=True,
            key=f"annotation_{indicator_id}_{horizon}",
        )
    with c2:
        chosen_region = st.selectbox(
            "🌐 地域ジャンプ(エリア絞り込み)",
            options=list(REGION_BOUNDS.keys()),
            index=0,
            key=f"region_zoom_{indicator_id}_{horizon}",
        )
    annotation_mode: AnnotationMode = _ANNOTATION_OPTIONS[chosen_label]

    # --- 詳細設定(折りたたみ): 主要都市・非日常スポット・県絞り込み ---
    # 2026-07-12: コントロール過多による認知負荷を軽減するため、使用頻度の
    # 低い設定を expander に集約(デフォルト畳んだ状態).
    show_cities = True
    show_spots = False
    chosen_pref_code: str | None = None
    selected_categories: list[str] = []
    with st.expander("⚙️ 詳細設定(主要都市・観光スポット・県ズーム)", expanded=False):
        s0, s1 = st.columns([1.2, 1.8])
        with s0:
            show_cities = st.checkbox(
                "主要都市マーカー",
                value=True,
                key=f"major_cities_{indicator_id}_{horizon}",
            )
        with s1:
            show_spots = st.checkbox(
                "✨ 非日常スポットを地図に重ねる",
                value=False,
                key=f"show_spots_{indicator_id}_{horizon}",
            )

        pref_options = ["全国(選択しない)"] + [
            f"{code} {name}" for code, name in PREFECTURE_NAMES.items()
        ]
        chosen_pref = st.selectbox(
            "🎯 都道府県を絞り込み(スポット詳細表示・地図ズーム)",
            options=pref_options,
            index=0,
            key=f"map_pref_filter_{indicator_id}_{horizon}",
        )
        if chosen_pref and not chosen_pref.startswith("全国"):
            chosen_pref_code = chosen_pref.split(" ", 1)[0]

        # スポットカテゴリ選択(チェック時のみ表示)
        if show_spots:
            st.markdown("**🏷️ 表示するカテゴリ**")
            cat_cols = st.columns(4)
            defaults_on = {"shrine_temple", "castle", "onsen", "viewpoint"}
            for i, cat in enumerate(_SPOT_CATEGORY_ORDER):
                icon, label, _ = CATEGORY_LABELS.get(cat, ("📍", cat, ""))
                with cat_cols[i % 4]:
                    if st.checkbox(
                        f"{icon} {label}",
                        value=(cat in defaults_on),
                        key=f"spot_cat_{cat}_{indicator_id}_{horizon}",
                    ):
                        selected_categories.append(cat)
            if not chosen_pref_code:
                st.info(
                    "💡 スポットを表示するには **都道府県を絞り込み** で 1 県を選んでください。"
                    "(全国一括は処理が重くなるため対応していません)"
                )

    pack = cached_values_for(indicator_id, horizon)
    values = pack.values
    num_with_value = sum(1 for v in values.values() if v is not None)
    num_no_pred = 47 - num_with_value

    rich_hover = _build_rich_hover(indicator_id, horizon, values)

    # POI 取得(絞り込み県があり、スポット表示 ON、カテゴリ選択時のみ)
    pois: list[POI] = []
    if show_spots and chosen_pref_code and selected_categories:
        with st.spinner("非日常スポットを取得中…"):
            pois = _cached_pois(chosen_pref_code, tuple(selected_categories))

    # 県絞り込み時は地図ズーム(地域ジャンプより優先)
    effective_zoom = chosen_region
    if chosen_pref_code:
        # bbox から地域ジャンプ範囲を構築
        bbox = get_prefecture_bbox(chosen_pref_code, margin=0.55)
        if bbox:
            # REGION_BOUNDS は (lat_min, lat_max, lon_min, lon_max) 形式
            REGION_BOUNDS[f"_focus_{chosen_pref_code}"] = (bbox[0], bbox[2], bbox[1], bbox[3])
            effective_zoom = f"_focus_{chosen_pref_code}"

    fig = render_choropleth(
        values,
        indicator_label=f"{indicator_label}({horizon_label}) {INDICATOR_UNITS.get(indicator_id, '')}",
        annotation_mode=annotation_mode,
        reverse_color=is_lower_better,
        show_major_cities=show_cities,
        region_zoom=effective_zoom,
        rich_hover=rich_hover,
        pois=pois if pois else None,
    )
    st.plotly_chart(fig, use_container_width=True)

    # 地方別平均サマリー(2026-07-12、地理的クラスタ傾向を一目で把握できるようにする)
    _render_region_summary(values, reverse_color=is_lower_better)

    # 「地域の魅力」セクション(POI 一覧)
    if show_spots and chosen_pref_code and pois:
        _render_spotlight_section(chosen_pref_code, pois)

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


def _render_spotlight_section(pref_code: str, pois: list[POI]) -> None:
    """『地域の魅力』セクション: 取得した POI をカテゴリ別カードで表示."""
    pref_name = PREFECTURE_NAMES.get(pref_code, pref_code)
    st.markdown("---")
    st.markdown(f"### ✨ {pref_name} の地域の魅力({len(pois)} スポット)")
    st.caption(
        "OpenStreetMap から取得した非日常スポット。"
        "カテゴリ別に整理して表示しています。クリックで地図上の対応マーカーが確認できます。"
    )

    # カテゴリ別グルーピング
    by_cat: dict[str, list[POI]] = {}
    for p in pois:
        by_cat.setdefault(p.category, []).append(p)

    # カテゴリの優先順序で表示
    for cat in _SPOT_CATEGORY_ORDER + ("other",):
        items = by_cat.get(cat)
        if not items:
            continue
        icon, label, _ = CATEGORY_LABELS.get(cat, ("📍", cat, ""))
        with st.expander(f"{icon} {label}({len(items)} 件)", expanded=(cat == "shrine_temple")):
            # 3 列でカード表示、最大 12 件
            display_items = items[:12]
            cols = st.columns(3)
            for i, p in enumerate(display_items):
                with cols[i % 3]:
                    gmaps = f"https://www.google.com/maps/search/?api=1&query={p.lat},{p.lon}"
                    osm = (
                        f"https://www.openstreetmap.org/?mlat={p.lat}&mlon={p.lon}"
                        f"#map=15/{p.lat}/{p.lon}"
                    )
                    st.markdown(
                        f"**{icon} {p.name}**  \n"
                        f"📍 [Google Maps]({gmaps}) ｜ [OpenStreetMap]({osm})"
                    )
            if len(items) > 12:
                st.caption(f"…他 {len(items) - 12} 件(地図上にマーカー表示中)")

    st.caption("出典: © OpenStreetMap contributors(ODbL)")
