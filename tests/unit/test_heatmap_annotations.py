"""ヒートマップ ラベル(annotation_mode)のロジック検証.

annotation_mode:
- "off": ラベル無し(オーバーレイ trace 追加されない)
- "extremes": 上位 N + 下位 N(値 None は除外)
- "all": 47 都道府県全て(値 None は除外)
"""

from __future__ import annotations

import pytest

from app.features.map_view.components.heatmap import (
    PREFECTURE_SHORT_NAMES,
    _select_labeled_codes,
    load_japan_geojson,
    render_choropleth,
)


def test_prefecture_short_names_cover_47() -> None:
    assert len(PREFECTURE_SHORT_NAMES) == 47
    assert set(PREFECTURE_SHORT_NAMES.keys()) == {f"{i:02d}" for i in range(1, 48)}


def test_select_labeled_codes_off_returns_empty() -> None:
    values: dict[str, float | None] = {f"{i:02d}": float(i) for i in range(1, 48)}
    assert _select_labeled_codes(values, mode="off", extremes_n=5) == []


def test_select_labeled_codes_all_returns_only_non_none() -> None:
    values: dict[str, float | None] = {
        f"{i:02d}": (float(i) if i % 2 == 0 else None) for i in range(1, 48)
    }
    codes = _select_labeled_codes(values, mode="all", extremes_n=5)
    # None の都道府県は除外
    assert all(values[c] is not None for c in codes)
    # 偶数(2,4,...,46)= 23 都道府県
    assert len(codes) == 23


def test_select_labeled_codes_extremes_returns_top_and_bottom_n() -> None:
    """値が異なる 10+ 都道府県のうち上位 3 + 下位 3 を返す."""
    values: dict[str, float | None] = {
        "01": 1.0, "02": 2.0, "03": 3.0, "04": 4.0, "05": 5.0,
        "06": 6.0, "07": 7.0, "08": 8.0, "09": 9.0, "10": 10.0,
    }
    codes = _select_labeled_codes(values, mode="extremes", extremes_n=3)
    # 下位 3: 01, 02, 03 / 上位 3: 08, 09, 10
    assert set(codes) == {"01", "02", "03", "08", "09", "10"}
    assert len(codes) == 6


def test_select_labeled_codes_extremes_when_few_values() -> None:
    """有効値が 2N 以下なら全件を返す."""
    values: dict[str, float | None] = {"01": 1.0, "02": 2.0, "03": 3.0}
    codes = _select_labeled_codes(values, mode="extremes", extremes_n=5)
    assert set(codes) == {"01", "02", "03"}


def test_select_labeled_codes_extremes_ignores_none() -> None:
    values: dict[str, float | None] = {
        "01": 1.0, "02": None, "03": 3.0, "04": 4.0, "05": None, "06": 6.0,
    }
    codes = _select_labeled_codes(values, mode="extremes", extremes_n=2)
    # None を除外して 4 件 = 2N → 全件
    assert set(codes) == {"01", "03", "04", "06"}


def test_render_choropleth_with_extremes_adds_overlay_trace() -> None:
    """extremes モードで Scattergeo オーバーレイ trace(3 レイヤー)が追加される."""
    geojson = load_japan_geojson()
    if geojson is None:
        pytest.skip("GeoJSON 未配置")

    values: dict[str, float | None] = {f"{i:02d}": float(i) for i in range(1, 48)}
    fig = render_choropleth(
        values, indicator_label="テスト", annotation_mode="extremes",
        show_major_cities=False,
    )
    # choropleth(1) + scattergeo(3 = halo/name/value-pill) = 4 trace
    assert len(fig.data) == 4
    trace_types = {t.type for t in fig.data}
    assert "choropleth" in trace_types
    assert "scattergeo" in trace_types
    scatter_traces = [t for t in fig.data if t.type == "scattergeo"]
    assert len(scatter_traces) == 3


def test_render_choropleth_off_no_overlay() -> None:
    """off モードでは(都市マーカーOFFなら)Scattergeo trace は追加されない."""
    geojson = load_japan_geojson()
    if geojson is None:
        pytest.skip("GeoJSON 未配置")

    values: dict[str, float | None] = {f"{i:02d}": float(i) for i in range(1, 48)}
    fig = render_choropleth(
        values, indicator_label="テスト", annotation_mode="off",
        show_major_cities=False,
    )
    trace_types = {t.type for t in fig.data}
    assert "scattergeo" not in trace_types


def test_render_choropleth_all_overlay_includes_47() -> None:
    """all モードでは 47 都道府県の値が Scattergeo に乗る(2026-07-12: 密集対策で 1 trace).

    47 件は _DENSE_THRESHOLD(12)を超える「密集」表示のため、視認性のため
    県名ラベル(halo + name の 2 trace)を省略し、値ピル(1 trace)のみ描画する.
    (12 件以下なら extremes モードのテストの通り halo + name + value-pill = 3 trace.)
    """
    geojson = load_japan_geojson()
    if geojson is None:
        pytest.skip("GeoJSON 未配置")

    values: dict[str, float | None] = {f"{i:02d}": float(i) for i in range(1, 48)}
    fig = render_choropleth(
        values, indicator_label="テスト", annotation_mode="all",
        show_major_cities=False,
    )
    scatter_traces = [t for t in fig.data if t.type == "scattergeo"]
    # 密集(47件 > _DENSE_THRESHOLD)時は value-pill のみ = 1 trace
    assert len(scatter_traces) == 1
    for overlay in scatter_traces:
        assert len(overlay.text) == 47
        assert len(overlay.lon) == 47
        assert len(overlay.lat) == 47


def test_render_choropleth_dense_marker_smaller_than_sparse() -> None:
    """密集時(>12件)の値ピルは非密集時より marker size / font size が小さい(視認性維持)."""
    geojson = load_japan_geojson()
    if geojson is None:
        pytest.skip("GeoJSON 未配置")

    sparse_values: dict[str, float | None] = {f"{i:02d}": float(i) for i in range(1, 6)}  # 5件
    dense_values: dict[str, float | None] = {f"{i:02d}": float(i) for i in range(1, 48)}  # 47件

    sparse_fig = render_choropleth(
        sparse_values, indicator_label="テスト", annotation_mode="all", show_major_cities=False,
    )
    dense_fig = render_choropleth(
        dense_values, indicator_label="テスト", annotation_mode="all", show_major_cities=False,
    )
    sparse_pill = [t for t in sparse_fig.data if t.type == "scattergeo"][-1]
    dense_pill = [t for t in dense_fig.data if t.type == "scattergeo"][-1]
    assert dense_pill.marker.size < sparse_pill.marker.size
    assert dense_pill.textfont.size < sparse_pill.textfont.size


def test_render_choropleth_value_pill_has_white_marker() -> None:
    """値ピル(3 trace目)は白丸+黒枠で地図色との干渉を避ける."""
    geojson = load_japan_geojson()
    if geojson is None:
        pytest.skip("GeoJSON 未配置")

    values: dict[str, float | None] = {f"{i:02d}": float(i) for i in range(1, 48)}
    fig = render_choropleth(
        values, indicator_label="テスト", annotation_mode="all",
        show_major_cities=False,
    )
    scatter_traces = [t for t in fig.data if t.type == "scattergeo"]
    pill = scatter_traces[-1]  # 最後 = 値ピル(最前面)
    assert pill.marker.color == "white"
    assert pill.marker.line.color == "black"
    assert pill.textposition == "middle center"


def test_render_choropleth_major_cities_adds_one_trace() -> None:
    """show_major_cities=True で主要都市マーカー trace が 1 つ追加される."""
    geojson = load_japan_geojson()
    if geojson is None:
        pytest.skip("GeoJSON 未配置")

    values: dict[str, float | None] = {f"{i:02d}": float(i) for i in range(1, 48)}
    fig_with = render_choropleth(
        values, indicator_label="テスト", annotation_mode="off",
        show_major_cities=True,
    )
    fig_without = render_choropleth(
        values, indicator_label="テスト", annotation_mode="off",
        show_major_cities=False,
    )
    assert len(fig_with.data) == len(fig_without.data) + 1


def test_render_choropleth_region_zoom_uses_larger_labels_than_zenkoku() -> None:
    """地域ジャンプ(2026-07-12): 特定地域に絞り込むと「見えている県数」基準で
    密集判定が行われ、全国表示より大きく読みやすいラベル(県名+値)になる.

    47 都道府県全てに値がある状態で all モード表示した場合:
    - 全国表示: dense(47件)→ 値ピルのみ 1 trace、marker_size=15
    - 関東ズーム: 関東 7 県のみ視界内 → dense=False → halo+name+value の 3 trace、marker_size=26
    """
    geojson = load_japan_geojson()
    if geojson is None:
        pytest.skip("GeoJSON 未配置")

    values: dict[str, float | None] = {f"{i:02d}": float(i) for i in range(1, 48)}

    fig_zenkoku = render_choropleth(
        values, indicator_label="テスト", annotation_mode="all",
        show_major_cities=False, region_zoom="全国",
    )
    fig_kanto = render_choropleth(
        values, indicator_label="テスト", annotation_mode="all",
        show_major_cities=False, region_zoom="関東",
    )

    zenkoku_traces = [t for t in fig_zenkoku.data if t.type == "scattergeo"]
    kanto_traces = [t for t in fig_kanto.data if t.type == "scattergeo"]

    # 全国表示は密集(値ピルのみ 1 trace)
    assert len(zenkoku_traces) == 1
    # 関東ズームは非密集(halo + name + value-pill の 3 trace)
    assert len(kanto_traces) == 3

    zenkoku_pill = zenkoku_traces[-1]
    kanto_pill = kanto_traces[-1]
    assert kanto_pill.marker.size > zenkoku_pill.marker.size
    assert kanto_pill.textfont.size > zenkoku_pill.textfont.size


def test_render_choropleth_unknown_region_zoom_falls_back_to_zenkoku() -> None:
    """未知の region_zoom 値(例: "_focus_13")でも全国基準にフォールバックして例外にならない."""
    geojson = load_japan_geojson()
    if geojson is None:
        pytest.skip("GeoJSON 未配置")

    values: dict[str, float | None] = {f"{i:02d}": float(i) for i in range(1, 48)}
    fig = render_choropleth(
        values, indicator_label="テスト", annotation_mode="all",
        show_major_cities=False, region_zoom="_focus_13",
    )
    scatter_traces = [t for t in fig.data if t.type == "scattergeo"]
    assert len(scatter_traces) == 1  # 全国基準(dense)にフォールバック
