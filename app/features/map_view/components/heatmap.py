"""47都道府県のヒートマップ描画コンポーネント(Plotly choropleth).

参照: R2.3 5階層 + 色覚多様性配慮パレット(viridis)
GeoJSON は `seeds/japan_prefectures.geojson` から読み込む(`scripts/fetch_geojson.py` で取得).
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

import plotly.graph_objects as go

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
    color_scale: str = "viridis",
    annotation_mode: AnnotationMode = "off",
    extremes_n: int = 5,
) -> go.Figure:
    """都道府県コード → 値 の dict から Plotly Figure を作る.

    - `quality_status='no_prediction'` 等で None が入っている都道府県は灰色塗り(UX-D-01)
    - 全国分布の四分位で 5階層(R2.3)
    - GeoJSON 未配置時は棒グラフにフォールバック(UI が必ず動くように)
    - `annotation_mode='extremes'` で上位 N + 下位 N の都道府県名+値を引き出し線でラベル表示
    - `annotation_mode='all'` で 47 都道府県全てをラベル表示

    Args:
        values: {prefecture_code: value_or_None}.
        indicator_label: 凡例ラベル.
        color_scale: Plotly カラースケール名(viridis 推奨).
        annotation_mode: ラベル表示モード("off" / "extremes" / "all").
        extremes_n: extremes モード時に表示する上位・下位の都道府県数(片側).

    Returns:
        plotly.graph_objects.Figure.
    """
    geojson = load_japan_geojson()
    if geojson is None:
        return _fallback_bar(values, indicator_label)

    locations: list[int] = []
    z: list[float | None] = []
    customdata: list[str] = []
    for code, val in values.items():
        locations.append(_pref_code_to_geojson_id(code))
        z.append(val)
        customdata.append(code)

    fig = go.Figure(
        go.Choropleth(
            geojson=geojson,
            locations=locations,
            z=z,
            featureidkey=PREFECTURE_FEATURE_ID_KEY,
            colorscale=color_scale,
            colorbar={"title": indicator_label, "thickness": 12, "len": 0.6},
            marker_line_color="white",
            marker_line_width=0.4,
            customdata=customdata,
            hovertemplate="<b>%{customdata}</b><br>%{z:.2f}<extra></extra>",
        )
    )

    # ラベル(引き出し線)を重ねる
    if annotation_mode != "off":
        labeled_codes = _select_labeled_codes(values, annotation_mode, extremes_n)
        _add_label_overlay(fig, values, labeled_codes)

    fig.update_geos(
        fitbounds="locations",
        visible=False,
        projection_type="mercator",
        bgcolor="rgba(0,0,0,0)",
    )
    fig.update_layout(
        margin={"r": 0, "t": 30, "l": 0, "b": 0},
        height=600,
        title={"text": indicator_label, "x": 0.5},
        showlegend=False,
    )
    return fig


def _select_labeled_codes(
    values: dict[str, float | None],
    mode: AnnotationMode,
    extremes_n: int,
) -> list[str]:
    """ラベル表示する都道府県コードのリスト."""
    if mode == "all":
        return [c for c, v in values.items() if v is not None]
    if mode == "extremes":
        with_values = [(c, v) for c, v in values.items() if v is not None]
        with_values.sort(key=lambda kv: kv[1])
        if len(with_values) <= 2 * extremes_n:
            return [c for c, _ in with_values]
        # 上位 N + 下位 N
        return [c for c, _ in with_values[:extremes_n]] + [c for c, _ in with_values[-extremes_n:]]
    return []


def _add_label_overlay(
    fig: go.Figure,
    values: dict[str, float | None],
    codes_to_label: list[str],
) -> None:
    """choropleth に Scattergeo オーバーレイで都道府県名+値ラベルを追加.

    視認性向上のため3レイヤー構成:
        1. 都道府県名(白)を太字でハロ(縁取り)として描画.
        2. 都道府県名(黒)を上記の前面に重ねる.
        3. 値は白い丸ピン(マーカー)の中に黒太字で配置(地図色に左右されない).
    """
    if not codes_to_label:
        return

    centroids = prefecture_centroids()
    lons: list[float] = []
    lats: list[float] = []
    name_texts: list[str] = []
    val_texts: list[str] = []
    for code in codes_to_label:
        if code not in centroids:
            continue
        val = values.get(code)
        lat, lon = centroids[code]
        name = PREFECTURE_SHORT_NAMES.get(code, code)
        lons.append(lon)
        lats.append(lat)
        name_texts.append(name)
        val_texts.append(f"{val:.1f}" if val is not None else "—")

    if not lons:
        return

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
                "size": 26,
                "color": "white",
                "line": {"width": 1.4, "color": "black"},
                "opacity": 0.95,
            },
            textfont={"family": "Arial Black", "size": 10, "color": "black"},
            textposition="middle center",
            hoverinfo="skip",
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
