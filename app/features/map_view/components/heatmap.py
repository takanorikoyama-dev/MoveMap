"""47都道府県のヒートマップ描画コンポーネント(Plotly choropleth).

参照: R2.3 5階層 + 色覚多様性配慮パレット(viridis)
GeoJSON は `seeds/japan_prefectures.geojson` から読み込む(`scripts/fetch_geojson.py` で取得).
"""

from __future__ import annotations

import json
from functools import lru_cache
from typing import Any, Literal

import plotly.graph_objects as go

from app.features.map_view.osm import CATEGORY_LABELS, POI
from app.features.map_view.regions import MAJOR_CITIES, REGION_BOUNDS, medal_for_rank
from app.shared.config import PROJECT_ROOT
from app.shared.geo import prefecture_centroids
from app.shared.logger import get_logger

AnnotationMode = Literal["off", "extremes", "all"]

# 都道府県名(短縮)
PREFECTURE_SHORT_NAMES: dict[str, str] = {
    "01": "北海道", "02": "青森", "03": "岩手", "04": "宮城", "05": "秋田",
    "06": "山形", "07": "福島", "08": "茨城", "09": "栃木", "10": "群馬",
    "11": "埼玉", "12": "千葉", "13": "東京", "14": "神奈川", "15": "新潟",
    "16": "富山", "17": "石川", "18": "福井", "19": "山梨", "20": "長野",
    "21": "岐阜", "22": "静岡", "23": "愛知", "24": "三重", "25": "滋賀",
    "26": "京都", "27": "大阪", "28": "兵庫", "29": "奈良", "30": "和歌山",
    "31": "鳥取", "32": "島根", "33": "岡山", "34": "広島", "35": "山口",
    "36": "徳島", "37": "香川", "38": "愛媛", "39": "高知", "40": "福岡",
    "41": "佐賀", "42": "長崎", "43": "熊本", "44": "大分", "45": "宮崎",
    "46": "鹿児島", "47": "沖縄",
}

logger = get_logger(__name__)

GEOJSON_PATH = PROJECT_ROOT / "seeds" / "japan_prefectures.geojson"
# dataofjapan の japan.geojson は `feature.properties.id`(整数 1〜47)に都道府県 ID を持つ.
# `feature.id` は None なので、Plotly の `featureidkey` には `properties.id` を指定する必要がある.
PREFECTURE_FEATURE_ID_KEY = "properties.id"


@lru_cache(maxsize=1)
def load_japan_geojson() -> dict[str, Any] | None:
    """日本47都道府県 GeoJSON を読み込む(キャッシュ).

    Returns:
        GeoJSON dict、または None(ファイル未配置時).
    """
    if not GEOJSON_PATH.exists():
        logger.warning(
            f"GeoJSON が未配置です: {GEOJSON_PATH}。"
            "`uv run python scripts/fetch_geojson.py` を実行してください。"
        )
        return None
    try:
        return json.loads(GEOJSON_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        logger.exception(f"GeoJSON のパース失敗: {GEOJSON_PATH}")
        return None


def _pref_code_to_geojson_id(code: str) -> int:
    """JIS X 0401 ('01' 〜 '47') を dataofjapan の id (1〜47) にマップ."""
    return int(code)


def render_choropleth(
    values: dict[str, float | None],
    indicator_label: str,
    color_scale: str = "RdYlGn",
    annotation_mode: AnnotationMode = "off",
    extremes_n: int = 5,
    reverse_color: bool = False,
    show_major_cities: bool = True,
    region_zoom: str = "全国",
    rich_hover: dict[str, dict[str, object]] | None = None,
    pois: list[POI] | None = None,
) -> go.Figure:
    """都道府県コード → 値 の dict から Plotly Figure を作る.

    R2.3 5階層 + 色覚多様性配慮(RdYlGn は緑=良い, 赤=悪い でユニバーサル).
    direction("低いほど良い" 指標)では `reverse_color=True` で色を反転し、
    どの指標でも「緑=住みやすい」になるよう統一する.

    Args:
        values: {prefecture_code: value_or_None}.
        indicator_label: 凡例ラベル.
        color_scale: Plotly カラースケール名(RdYlGn 推奨).
        annotation_mode: ラベル表示モード("off" / "extremes" / "all").
        extremes_n: extremes モード時に表示する上位・下位の都道府県数(片側).
        reverse_color: True で住みやすさ方向反転(値が低いほど緑になる).
        show_major_cities: True で主要 11 都市マーカーをオーバーレイ.
        region_zoom: '全国' or REGIONS のいずれかで初期表示範囲を変更.
        rich_hover: {pref_code: {label, value_unit, rank, composite, stars}} 形式の
            拡張ツールチップ情報. 渡されると hovertemplate に組み込まれる.
    """
    geojson = load_japan_geojson()
    if geojson is None:
        return _fallback_bar(values, indicator_label)

    locations: list[int] = []
    z: list[float | None] = []
    customdata: list[list[object]] = []
    for code, val in values.items():
        locations.append(_pref_code_to_geojson_id(code))
        z.append(val)
        info = (rich_hover or {}).get(code, {})
        customdata.append(
            [
                code,
                info.get("name", PREFECTURE_SHORT_NAMES.get(code, code)),
                info.get("value_unit", ""),
                info.get("rank", "—"),
                info.get("composite", "—"),
                info.get("stars", ""),
            ]
        )

    hovertemplate = (
        "<b>%{customdata[1]}(%{customdata[0]})</b><br>"
        "値: %{z:,.2f}%{customdata[2]}<br>"
        "総合偏差値: %{customdata[4]}<br>"
        "順位: %{customdata[3]} / 47<br>"
        "★: %{customdata[5]}<extra></extra>"
    )

    fig = go.Figure(
        go.Choropleth(
            geojson=geojson,
            locations=locations,
            z=z,
            featureidkey=PREFECTURE_FEATURE_ID_KEY,
            colorscale=color_scale,
            reversescale=reverse_color,
            colorbar={
                "title": {"text": indicator_label, "font": {"size": 13}},
                "thickness": 14,
                "len": 0.7,
            },
            marker_line_color="#666",
            marker_line_width=0.5,
            customdata=customdata,
            hovertemplate=hovertemplate,
        )
    )

    # 全国平均ライン(カラーバー内の白破線)
    valid_vals = [v for v in z if v is not None]
    if valid_vals:
        mean_val = sum(valid_vals) / len(valid_vals)
        fig.add_annotation(
            text=f"全国平均: {mean_val:,.1f}",
            xref="paper", yref="paper",
            x=1.02, y=0.92, xanchor="left", showarrow=False,
            font={"size": 10, "color": "#444"},
        )

    # ラベル(引き出し線 + メダル)
    # 2026-07-12: 地域ジャンプで特定地域に絞り込んだ場合、その地域内に実際に
    # 見えている県数を基準に密集判定する(全国基準の小さいラベルのままにしない).
    if annotation_mode != "off":
        labeled_codes = _select_labeled_codes(values, annotation_mode, extremes_n, reverse_color)
        active_bounds = REGION_BOUNDS.get(region_zoom, REGION_BOUNDS["全国"])
        _add_label_overlay(fig, values, labeled_codes, reverse_color, active_bounds=active_bounds)

    if show_major_cities:
        _add_major_city_markers(fig)

    # POI レイヤー(観光・温泉・神社仏閣などのスポット)
    if pois:
        _add_poi_layers(fig, pois)

    # 地域ジャンプ
    if region_zoom and region_zoom != "全国" and region_zoom in REGION_BOUNDS:
        lat_min, lat_max, lon_min, lon_max = REGION_BOUNDS[region_zoom]
        fig.update_geos(
            visible=False,
            projection_type="mercator",
            bgcolor="rgba(0,0,0,0)",
            lataxis_range=[lat_min, lat_max],
            lonaxis_range=[lon_min, lon_max],
        )
    else:
        fig.update_geos(
            fitbounds="locations",
            visible=False,
            projection_type="mercator",
            bgcolor="rgba(248,250,252,0.4)",  # 淡いグレートーン
        )

    fig.update_layout(
        margin={"r": 0, "t": 40, "l": 0, "b": 0},
        height=540,  # 縦長スマホ + 通常デスクトップの両立点
        title={
            "text": f"<b>{indicator_label}</b>",
            "x": 0.5,
            "font": {"size": 17, "color": "#1f4068"},
        },
        showlegend=False,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )
    return fig


def _select_labeled_codes(
    values: dict[str, float | None],
    mode: AnnotationMode,
    extremes_n: int,
    reverse_color: bool = False,
) -> list[str]:
    """ラベル表示する都道府県コードのリスト. reverse_color=True なら住みやすさ順を反転."""
    if mode == "all":
        return [c for c, v in values.items() if v is not None]
    if mode == "extremes":
        with_values = [(c, v) for c, v in values.items() if v is not None]
        with_values.sort(key=lambda kv: kv[1])
        if len(with_values) <= 2 * extremes_n:
            return [c for c, _ in with_values]
        # 上位 N + 下位 N(値ベース)
        return [c for c, _ in with_values[:extremes_n]] + [c for c, _ in with_values[-extremes_n:]]
    return []


def _ranked_top_codes(
    values: dict[str, float | None],
    n: int,
    higher_is_better: bool,
) -> list[str]:
    """住みやすさ方向で上位 N の都道府県コード(メダル表示用)."""
    with_values = [(c, v) for c, v in values.items() if v is not None]
    with_values.sort(key=lambda kv: kv[1], reverse=higher_is_better)
    return [c for c, _ in with_values[:n]]


_DENSE_THRESHOLD = 12
"""この件数を超えるラベル表示は「密集」とみなし、視認性のためサイズ縮小 + 県名ラベル省略."""


def _add_label_overlay(
    fig: go.Figure,
    values: dict[str, float | None],
    codes_to_label: list[str],
    reverse_color: bool = False,
    active_bounds: tuple[float, float, float, float] | None = None,
) -> None:
    """choropleth に Scattergeo オーバーレイで都道府県名+値ラベルを追加.

    視認性向上のため3レイヤー構成:
        1. 都道府県名(白)を太字でハロ(縁取り)として描画.
        2. 都道府県名(黒)を上記の前面に重ねる.
        3. 値は白い丸ピン(マーカー)の中に黒太字で配置(地図色に左右されない).

    2026-07-12: 「47都道府県すべて表示」モードでは件数が多く(dense)、
    県名ラベルまで出すと密集地域(関東等)で重なって読めなくなるため、
    dense 時は県名レイヤーを省略し値ピンのみ縮小表示する(クラッター対策).

    密集判定は「実際に画面内に見えている県数」(active_bounds 内)を基準にする.
    地域ジャンプで関東等に絞り込んだ場合、全国基準では 47 件で dense=True の
    ままだったが、実際に見えているのは 7 県程度なので dense=False とし、
    大きく読みやすいラベル(県名+値)で表示する.
    """
    if not codes_to_label:
        return

    centroids = prefecture_centroids()

    if active_bounds is not None:
        lat_min, lat_max, lon_min, lon_max = active_bounds
        visible_count = sum(
            1 for c in codes_to_label
            if c in centroids
            and lat_min <= centroids[c][0] <= lat_max
            and lon_min <= centroids[c][1] <= lon_max
        )
    else:
        visible_count = len(codes_to_label)

    dense = visible_count > _DENSE_THRESHOLD
    marker_size = 15 if dense else 26
    value_font_size = 8 if dense else 10
    lons: list[float] = []
    lats: list[float] = []
    name_texts: list[str] = []
    val_texts: list[str] = []
    # 住みやすさ方向で上位 3 にメダル
    medal_codes = set(_ranked_top_codes(values, 3, higher_is_better=not reverse_color))
    medal_map = {c: medal_for_rank(i + 1) for i, c in enumerate(
        _ranked_top_codes(values, 3, higher_is_better=not reverse_color)
    )}
    for code in codes_to_label:
        if code not in centroids:
            continue
        val = values.get(code)
        lat, lon = centroids[code]
        base_name = PREFECTURE_SHORT_NAMES.get(code, code)
        name = f"{medal_map[code]} {base_name}" if code in medal_codes else base_name
        lons.append(lon)
        lats.append(lat)
        name_texts.append(name)
        val_texts.append(f"{val:.1f}" if val is not None else "—")

    if not lons:
        return

    if not dense:
        # Layer 1: 都道府県名のハロ(白・太字、わずかに大きく)
        fig.add_trace(
            go.Scattergeo(
                lon=lons,
                lat=lats,
                text=name_texts,
                mode="text",
                textfont={"family": "Arial Black", "size": 13, "color": "white"},
                textposition="top center",
                hoverinfo="skip",
                showlegend=False,
            )
        )
        # Layer 2: 都道府県名(黒太字)
        fig.add_trace(
            go.Scattergeo(
                lon=lons,
                lat=lats,
                text=name_texts,
                mode="text",
                textfont={"family": "Arial Black", "size": 12, "color": "black"},
                textposition="top center",
                hoverinfo="skip",
                showlegend=False,
            )
        )
    # Layer 3: 値を白丸ピン+黒太字でセンタリング(地図塗り色と干渉しない)
    fig.add_trace(
        go.Scattergeo(
            lon=lons,
            lat=lats,
            text=val_texts,
            mode="markers+text",
            marker={
                "size": marker_size,
                "color": "white",
                "line": {"width": 1.2, "color": "black"},
                "opacity": 0.95,
            },
            textfont={"family": "Arial Black", "size": value_font_size, "color": "black"},
            textposition="middle center",
            hoverinfo="skip",
            showlegend=False,
        )
    )


def _add_poi_layers(fig: go.Figure, pois: list[POI]) -> None:
    """POI をカテゴリ別に色分けして地図に重ねる(凡例付き)."""
    by_category: dict[str, list[POI]] = {}
    for p in pois:
        by_category.setdefault(p.category, []).append(p)
    for category, items in by_category.items():
        meta = CATEGORY_LABELS.get(category, ("📍", category, "#888"))
        icon, label, color = meta
        fig.add_trace(
            go.Scattergeo(
                lon=[p.lon for p in items],
                lat=[p.lat for p in items],
                text=[f"{icon} {p.name}" for p in items],
                mode="markers",
                marker={
                    "size": 9,
                    "color": color,
                    "opacity": 0.85,
                    "symbol": "circle",
                    "line": {"width": 1.2, "color": "white"},
                },
                hovertemplate="<b>%{text}</b><extra></extra>",
                name=f"{icon} {label}",
                showlegend=True,
                legendgroup="poi",
            )
        )
    # 凡例の表示位置を地図右上に
    fig.update_layout(
        showlegend=True,
        legend={
            "orientation": "v",
            "yanchor": "top",
            "y": 0.98,
            "xanchor": "left",
            "x": 1.02,
            "bgcolor": "rgba(255,255,255,0.9)",
            "bordercolor": "#d8e0ea",
            "borderwidth": 1,
            "font": {"size": 11},
        },
    )


def _add_major_city_markers(fig: go.Figure) -> None:
    """主要 11 都市マーカーを重ねる(青い小さなピン + ラベル)."""
    lons = [c[3] for c in MAJOR_CITIES]
    lats = [c[2] for c in MAJOR_CITIES]
    names = [c[1] for c in MAJOR_CITIES]
    fig.add_trace(
        go.Scattergeo(
            lon=lons,
            lat=lats,
            text=names,
            mode="markers+text",
            marker={
                "size": 8,
                "color": "#1f4068",
                "symbol": "circle",
                "line": {"width": 1.2, "color": "white"},
            },
            textfont={"family": "Arial", "size": 9, "color": "#1f4068"},
            textposition="bottom right",
            hoverinfo="text",
            hovertemplate="<b>%{text}</b><extra></extra>",
            name="主要都市",
            showlegend=False,
        )
    )


def _fallback_bar(values: dict[str, float | None], indicator_label: str) -> go.Figure:
    """GeoJSON が無い環境向けのフォールバック表示(棒グラフ)."""
    sortable = [(code, val) for code, val in values.items() if val is not None]
    sortable.sort(key=lambda x: x[1], reverse=True)
    codes = [c for c, _ in sortable]
    vals = [v for _, v in sortable]

    fig = go.Figure(go.Bar(x=codes, y=vals, marker={"color": vals, "colorscale": "viridis"}))
    fig.update_layout(
        title=f"{indicator_label}(GeoJSON 未配置: フォールバック棒グラフ)",
        xaxis_title="都道府県コード",
        yaxis_title=indicator_label,
        height=600,
    )
    return fig
