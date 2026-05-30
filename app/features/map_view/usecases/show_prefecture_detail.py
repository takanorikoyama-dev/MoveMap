"""SF-004 ShowPrefectureDetail — 1都道府県の全指標×4時点を詳細表示.

参照: outputs/06_system_design/05_画面設計.md (SCR-002)
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from app.features.map_view._cache import cached_prefecture_full_table
from app.features.map_view.usecases.switch_horizon import HORIZON_LABELS
from app.features.map_view.usecases.switch_indicator import INDICATOR_LABELS
from app.features.map_view.wikipedia import (
    WikiInfo,
    fetch_wiki_info,
    get_all_municipalities_for,
    get_municipalities_for,
)


@st.cache_data(ttl=3600, show_spinner=False)
def _cached_wiki_info(wiki_title: str) -> WikiInfo | None:
    """Wikipedia 取得結果をキャッシュ(1 時間)."""
    return fetch_wiki_info(wiki_title)

PREFECTURE_NAMES: dict[str, str] = {
    "01": "北海道", "02": "青森県", "03": "岩手県", "04": "宮城県", "05": "秋田県",
    "06": "山形県", "07": "福島県", "08": "茨城県", "09": "栃木県", "10": "群馬県",
    "11": "埼玉県", "12": "千葉県", "13": "東京都", "14": "神奈川県", "15": "新潟県",
    "16": "富山県", "17": "石川県", "18": "福井県", "19": "山梨県", "20": "長野県",
    "21": "岐阜県", "22": "静岡県", "23": "愛知県", "24": "三重県", "25": "滋賀県",
    "26": "京都府", "27": "大阪府", "28": "兵庫県", "29": "奈良県", "30": "和歌山県",
    "31": "鳥取県", "32": "島根県", "33": "岡山県", "34": "広島県", "35": "山口県",
    "36": "徳島県", "37": "香川県", "38": "愛媛県", "39": "高知県", "40": "福岡県",
    "41": "佐賀県", "42": "長崎県", "43": "熊本県", "44": "大分県", "45": "宮崎県",
    "46": "鹿児島県", "47": "沖縄県",
}


def show_prefecture_detail(prefecture_code: str) -> None:
    """指定都道府県の詳細パネルを表示する.

    Args:
        prefecture_code: JIS X 0401 都道府県コード.
    """
    name = PREFECTURE_NAMES.get(prefecture_code, prefecture_code)
    st.subheader(f"{name}({prefecture_code})詳細")

    table = cached_prefecture_full_table(prefecture_code)

    rows: list[dict[str, str]] = []
    for indicator_id, indicator_label in INDICATOR_LABELS.items():
        row: dict[str, str] = {"指標": indicator_label}
        per_horizon = table.get(indicator_id, {})
        for horizon, horizon_label in HORIZON_LABELS.items():
            val = per_horizon.get(horizon)  # type: ignore[arg-type]
            row[horizon_label] = _format_value(indicator_id, val)
        rows.append(row)

    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True, hide_index=True)
    st.caption("※ 予測対象外の指標(空気質/災害リスク/交通アクセス)は予測列を「—」表示しています。")

    # ---- 市区町村セクション(写真 + 概要)----
    _render_municipality_section(prefecture_code, name)

    # ---- すべての市区町村を検索(全 1,742 件)----
    _render_municipality_search(prefecture_code, name)


def _render_municipality_section(prefecture_code: str, prefecture_name: str) -> None:
    """主要 5 市区町村の写真 + 概要 + 観光/文化セクションを表示."""
    municipalities = get_municipalities_for(prefecture_code)
    if not municipalities:
        return

    st.markdown("---")
    st.markdown(f"### 🏙️ {prefecture_name} の主要な市区町村")
    st.caption(
        "各市区町村の街並み・観光・文化を Wikipedia + Wikimedia Commons から取得。"
        "「もっと見る」で写真ギャラリーと観光情報が展開されます。"
    )

    # まず上段に「サムネ + 名前」のコンパクトな 5 枚カード
    thumb_cols = st.columns(len(municipalities))
    for col, m in zip(thumb_cols, municipalities):
        with col:
            with st.container(border=True):
                info = _cached_wiki_info(m["wiki_title"])
                if info and info.image_url:
                    st.image(info.image_url, use_container_width=True)
                else:
                    st.markdown("📷 *(画像なし)*")
                st.markdown(f"**{m['name']}**")
                if info and info.extract:
                    text = info.extract[:80] + ("…" if len(info.extract) > 80 else "")
                    st.caption(text)

    # 下段に「もっと見る」展開エリア(全市区町村が縦に並ぶ)
    st.markdown("#### 📖 詳しく見る(クリックで展開)")
    for m in municipalities:
        info = _cached_wiki_info(m["wiki_title"])
        with st.expander(f"🏛️ {m['name']} の街並み・観光・文化", expanded=False):
            if not info:
                st.warning("情報を取得できませんでした。")
                continue

            # ヒーロー写真 + 詳細概要
            top_cols = st.columns([1, 2])
            with top_cols[0]:
                if info.image_url:
                    st.image(info.image_url, use_container_width=True)
            with top_cols[1]:
                st.markdown(f"**{info.title}**")
                if info.extract:
                    st.markdown(info.extract)
                st.markdown(f"[🔗 Wikipedia で全文を読む]({info.page_url})")

            # 写真ギャラリー(複数列)
            if info.gallery_urls:
                st.markdown("**📷 街並み・風景ギャラリー**")
                gallery_cols = st.columns(min(3, len(info.gallery_urls)))
                for i, url in enumerate(info.gallery_urls[:6]):
                    with gallery_cols[i % len(gallery_cols)]:
                        st.image(url, use_container_width=True)

            # 統計データ(Wikidata から)
            if info.stats:
                _render_stats_panel(info.stats)

            # 地図(OpenStreetMap iframe、Wikidata 座標があれば)
            if info.stats and info.stats.latitude and info.stats.longitude:
                _render_osm_map(info.stats.latitude, info.stats.longitude, info.title)

            # 観光・文化・街並みセクションリンク
            if info.sections:
                st.markdown("**🎯 観光・文化・街並み・産業の情報**")
                sec_cols = st.columns(min(4, len(info.sections)))
                for i, sec in enumerate(info.sections):
                    with sec_cols[i % len(sec_cols)]:
                        st.markdown(f"🔗 [{sec.name}]({sec.anchor})")
                st.caption("各リンクをクリックすると Wikipedia の該当セクションに移動します。")

    st.caption(
        "出典: Wikipedia / Wikimedia Commons(CC-BY-SA)。"
        "写真はリンクのみで提供。再配布はしておりません。"
    )


def _render_municipality_search(prefecture_code: str, prefecture_name: str) -> None:
    """都道府県内の全市区町村から 1 件選んで詳細表示するセクション."""
    all_munis = get_all_municipalities_for(prefecture_code)
    if not all_munis:
        return

    st.markdown("---")
    st.markdown(f"### 🔍 {prefecture_name}内のすべての市区町村を検索")
    st.caption(
        f"{prefecture_name} には全 **{len(all_munis)} 市区町村** があります。"
        "気になる地域を選ぶと、Wikipedia から街並み・統計・地図を取得して表示します。"
    )

    options = [""] + [m["name"] for m in all_munis]
    chosen_name = st.selectbox(
        f"市区町村を選択(検索可、{prefecture_name}内 {len(all_munis)} 件)",
        options=options,
        index=0,
        key=f"muni_search_{prefecture_code}",
        placeholder="市区町村名を入力 / リストから選択…",
    )
    if not chosen_name:
        return

    selected = next((m for m in all_munis if m["name"] == chosen_name), None)
    if not selected:
        return

    info = _cached_wiki_info(selected["wiki_title"])
    with st.container(border=True):
        st.markdown(f"#### 🏛️ {selected['name']} の詳細")
        st.caption(f"JIS 市区町村コード: {selected['jis_code']}")
        if not info:
            st.warning(
                "Wikipedia から情報を取得できませんでした。"
                "ページ名が完全一致しない可能性があります。"
            )
            return

        # ヒーロー写真 + 概要
        top_cols = st.columns([1, 2])
        with top_cols[0]:
            if info.image_url:
                st.image(info.image_url, use_container_width=True)
            else:
                st.markdown("📷 *(画像なし)*")
        with top_cols[1]:
            st.markdown(f"**{info.title}**")
            if info.extract:
                st.markdown(info.extract)
            st.markdown(f"[🔗 Wikipedia で全文を読む]({info.page_url})")

        # ギャラリー
        if info.gallery_urls:
            st.markdown("**📷 街並み・風景ギャラリー**")
            gallery_cols = st.columns(min(3, len(info.gallery_urls)))
            for i, url in enumerate(info.gallery_urls[:6]):
                with gallery_cols[i % len(gallery_cols)]:
                    st.image(url, use_container_width=True)

        # 統計 + マップ
        if info.stats:
            _render_stats_panel(info.stats)
        if info.stats and info.stats.latitude and info.stats.longitude:
            _render_osm_map(info.stats.latitude, info.stats.longitude, info.title)

        # 観光・文化セクションリンク
        if info.sections:
            st.markdown("**🎯 観光・文化・街並み・産業の情報**")
            sec_cols = st.columns(min(4, len(info.sections)))
            for i, sec in enumerate(info.sections):
                with sec_cols[i % len(sec_cols)]:
                    st.markdown(f"🔗 [{sec.name}]({sec.anchor})")


def _render_stats_panel(stats) -> None:  # type: ignore[no-untyped-def]
    """Wikidata 統計を 4 カラムのメトリクスで表示."""
    st.markdown("**📊 基礎統計データ(Wikidata より)**")
    cols = st.columns(4)
    with cols[0]:
        st.metric(
            "人口",
            f"{stats.population:,} 人" if stats.population else "—",
        )
    with cols[1]:
        st.metric(
            "面積",
            f"{stats.area_km2:,.1f} km²" if stats.area_km2 else "—",
        )
    with cols[2]:
        # 人口密度を算出
        if stats.population and stats.area_km2 and stats.area_km2 > 0:
            density = stats.population / stats.area_km2
            st.metric("人口密度", f"{density:,.0f} 人/km²")
        else:
            st.metric("人口密度", "—")
    with cols[3]:
        st.metric(
            "標高",
            f"{stats.elevation_m:,.0f} m" if stats.elevation_m else "—",
        )


def _render_osm_map(lat: float, lon: float, title: str) -> None:
    """OpenStreetMap の埋込マップ(マーカー付き)."""
    st.markdown("**🗺️ 位置・地図**")
    margin = 0.04  # ~4km 程度の表示範囲
    bbox = f"{lon - margin},{lat - margin},{lon + margin},{lat + margin}"
    osm_url = (
        f"https://www.openstreetmap.org/export/embed.html"
        f"?bbox={bbox}&layer=mapnik&marker={lat},{lon}"
    )
    html = (
        f'<iframe width="100%" height="380" frameborder="0" scrolling="no" '
        f'src="{osm_url}" style="border: 1px solid #d8e0ea; border-radius: 6px;"></iframe>'
    )
    st.markdown(html, unsafe_allow_html=True)
    gsi_url = f"https://maps.gsi.go.jp/?ll={lat},{lon}&z=13&base=std"
    st.markdown(
        f"🌐 [{title} を OpenStreetMap で開く]"
        f"(https://www.openstreetmap.org/?mlat={lat}&mlon={lon}#map=13/{lat}/{lon}) ｜ "
        f"🗾 [国土地理院 地形図で見る]({gsi_url})"
    )


def _format_value(indicator_id: str, val: float | None) -> str:
    """指標に応じて値を整形表示.

    - 地価 / 賃料: ¥ 記号 + 千区切り + 小数点なし(例: ¥937,111)
    - 出生数: 千区切り + 「人」(例: 84,207 人)
    - 物価変動率: 小数 1 桁(例: 102.6)
    - 空気質(AQI): 整数(例: 55)
    - 災害リスク / 交通アクセス: 小数 2 桁(0-5 スコア)
    """
    if val is None:
        return "—"
    if indicator_id == "land_price":
        return f"¥{int(round(val)):,}/㎡"
    if indicator_id == "rent_index":
        return f"¥{int(round(val)):,}/月"
    if indicator_id == "birth_count":
        return f"{int(round(val)):,} 人"
    if indicator_id == "price_index":
        return f"{val:.1f}"
    if indicator_id == "air_quality":
        return f"{int(round(val))}"
    if indicator_id == "public_safety":
        return f"{int(round(val)):,} 件"
    if indicator_id == "net_migration":
        return f"{val:+.2f}‰"
    return f"{val:.2f}"
