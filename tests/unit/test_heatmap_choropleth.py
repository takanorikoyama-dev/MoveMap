"""ヒートマップ(choropleth)の GeoJSON 解像度をテスト.

過去のバグ: `featureidkey="id"` を使っていたが、dataofjapan の japan.geojson は
`feature.id` が None で `feature.properties.id` に都道府県 ID(int 1〜47)を持つ.
→ Plotly がどの location ともマッチできず、地図が空白で描画された.
"""

from __future__ import annotations

import pytest

from app.features.map_view.components.heatmap import (
    PREFECTURE_FEATURE_ID_KEY,
    _fallback_bar,
    _pref_code_to_geojson_id,
    load_japan_geojson,
    render_choropleth,
)


def test_feature_id_key_uses_properties_id() -> None:
    """`featureidkey` は `feature.properties.id` を指す."""
    assert PREFECTURE_FEATURE_ID_KEY == "properties.id"


def test_pref_code_to_geojson_id_converts_to_int() -> None:
    """JIS X 0401 '01' → 整数 1."""
    assert _pref_code_to_geojson_id("01") == 1
    assert _pref_code_to_geojson_id("13") == 13
    assert _pref_code_to_geojson_id("47") == 47


def test_geojson_properties_id_matches_jis_x_0401() -> None:
    """seeds/japan_prefectures.geojson 内の `properties.id` が 1〜47 を網羅."""
    geojson = load_japan_geojson()
    if geojson is None:
        pytest.skip("GeoJSON 未配置(`scripts/fetch_geojson.py` を実行してください)")

    ids = {f["properties"]["id"] for f in geojson["features"]}
    assert ids == set(range(1, 48)), f"properties.id が 1〜47 を網羅していない: 欠損 {set(range(1, 48)) - ids}"


def test_render_choropleth_uses_properties_id_key() -> None:
    """生成された Figure の trace に featureidkey='properties.id' が設定されている."""
    geojson = load_japan_geojson()
    if geojson is None:
        pytest.skip("GeoJSON 未配置")

    values: dict[str, float | None] = {f"{i:02d}": float(i) for i in range(1, 48)}
    fig = render_choropleth(values, indicator_label="テスト指標")

    assert len(fig.data) > 0
    trace = fig.data[0]
    # plotly.graph_objects.Choropleth のフィールド
    assert trace.featureidkey == "properties.id"


def test_render_choropleth_locations_are_ints_matching_geojson() -> None:
    """`locations` の整数値が GeoJSON の `properties.id` 集合と完全一致."""
    geojson = load_japan_geojson()
    if geojson is None:
        pytest.skip("GeoJSON 未配置")

    values: dict[str, float | None] = {f"{i:02d}": float(i) for i in range(1, 48)}
    fig = render_choropleth(values, indicator_label="テスト指標")
    trace = fig.data[0]

    location_set = set(trace.locations)
    geojson_ids = {f["properties"]["id"] for f in geojson["features"]}
    assert location_set == geojson_ids


def test_render_choropleth_handles_none_values() -> None:
    """None(予測なし)が混在しても Figure 生成は成功する."""
    geojson = load_japan_geojson()
    if geojson is None:
        pytest.skip("GeoJSON 未配置")

    values: dict[str, float | None] = {f"{i:02d}": (float(i) if i % 3 == 0 else None) for i in range(1, 48)}
    fig = render_choropleth(values, indicator_label="テスト指標")
    assert len(fig.data) > 0


def test_fallback_bar_when_no_geojson() -> None:
    """GeoJSON なしのフォールバックは棒グラフ(Bar trace)."""
    values: dict[str, float | None] = {"13": 100.0, "27": 95.0, "01": 110.0}
    fig = _fallback_bar(values, indicator_label="テスト")
    assert len(fig.data) > 0
    assert fig.data[0].type == "bar"
