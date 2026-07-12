"""TC-MV / TC-CP smoke: Streamlit アプリ全体が import + run できる.

参照: outputs/06_system_design/06_テスト設計.md (smoke カテゴリ)
INV-BIZ-005: 免責バナーが表示される
"""

from __future__ import annotations

from pathlib import Path

import pytest

streamlit_testing = pytest.importorskip("streamlit.testing.v1")
AppTest = streamlit_testing.AppTest


APP_PATH = Path(__file__).resolve().parents[2] / "app" / "main.py"


def _new_app() -> AppTest:
    # 6 タブの初期描画で compute_ranking が複数回走るため余裕を持って 90 秒
    return AppTest.from_file(str(APP_PATH), default_timeout=90)


def test_app_runs_without_exceptions() -> None:
    """`app/main.py` が import エラー / 実行エラーなく完走する."""
    at = _new_app()
    at.run()
    assert not at.exception, f"Streamlit app raised: {at.exception}"


def test_app_shows_disclaimer_banner() -> None:
    """INV-BIZ-005 + INV-BIZ-006(DEC-016 派生): 免責バナーが表示されている(warning 要素として存在).

    DEC-016 で文言を強化:「個人制作のポートフォリオ」+「投資/不動産取引/移住助言ではない」明示.
    """
    at = _new_app()
    at.run()
    # streamlit の st.warning は warning() で取得可能
    assert len(at.warning) >= 1
    # 免責テキストの主要キーワードを含む
    texts = " ".join(w.value for w in at.warning)
    assert "ポートフォリオ" in texts
    # INV-BIZ-006: 3 つの助言ではない明示
    assert "投資助言" in texts
    assert "移住助言" in texts


def test_app_renders_three_tabs() -> None:
    """MoveMap ブランドが画面に表示される(ヒーロー内、2026-06-02 デザイン刷新)."""
    at = _new_app()
    at.run()
    # st.title は廃止し、ブランド表示はヒーローの HTML 内に統合された.
    # ヒーロー HTML(movemap-hero クラス + MoveMap ブランドマーク)が
    # markdown 要素として注入されていることを確認.
    md_texts = " ".join(el.value for el in at.markdown if hasattr(el, "value"))
    assert "movemap-hero" in md_texts or "MoveMap" in md_texts


def test_app_home_view_has_section_banners() -> None:
    """ホーム画面に 6 つのセクション入口ボタンが存在.

    2026-06-02: 視覚バナーは HTML、クリック処理は st.button(信頼性のため).
    """
    at = _new_app()
    at.run()
    button_keys = {b.key for b in at.button if hasattr(b, "key") and b.key}
    expected_keys = {
        f"home_open_{k}"
        for k in ("diagnosis", "map", "ranking", "compare", "detail", "model")
    }
    assert expected_keys.issubset(button_keys), (
        f"バナーボタンが揃っていない: 期待 {expected_keys} / 実際 {button_keys}"
    )


def test_app_footer_links_point_to_internal_views() -> None:
    """INV-BIZ-008 + DEC-017: フッターの法務リンクがサイト内 view を指している.

    旧実装(GitHub の blob/training/outputs/legal/*.md)から、
    `?view=terms` / `?view=privacy` / `?view=contact` のサイト内遷移に変更.
    GitHub リポジトリリンクはフッターから削除済.
    """
    at = _new_app()
    at.run()
    md_html = " ".join(el.value for el in at.markdown if hasattr(el, "value"))
    # サイト内 view への 3 リンクが存在
    assert "?view=terms" in md_html, "利用規約のサイト内 view リンクが見つからない"
    assert "?view=privacy" in md_html, "プライバシーポリシーのサイト内 view リンクが見つからない"
    assert "?view=contact" in md_html, "お問い合わせのサイト内 view リンクが見つからない"
    # GitHub リポジトリへの直接リンクは削除されている
    assert "github.com/takanorikoyama-dev/MoveMap\"" not in md_html, (
        "GitHub リポジトリリンクは DEC-017 で削除されているはず"
    )
    # DEC-018: 全クレジット導線(seeds/image_credits.md)もフッターから削除
    assert "seeds/image_credits.md" not in md_html, (
        "DEC-018 で全クレジット導線は削除済み(個別画像近くの Photo: 表記は維持)"
    )


@pytest.mark.parametrize("view_name", ["terms", "privacy", "contact"])
def test_legal_views_render_without_errors(view_name: str) -> None:
    """法務系 3 view が ?view=KEY で開いた時に例外なく描画される(DEC-017)."""
    at = _new_app()
    at.query_params["view"] = view_name
    at.run()
    assert not at.exception, f"view={view_name} で例外: {at.exception}"
    # 各 view の冒頭にタイトル相当の h1/markdown が出ている(空ページではない)
    md_texts = " ".join(el.value for el in at.markdown if hasattr(el, "value"))
    assert len(md_texts) > 100, f"view={view_name} の描画が空に近い"


def test_ranking_view_default_indicator_selection_reduces_columns() -> None:
    """ランキング表: 横スクロール軽減のため、デフォルトで指標が 4 つに絞られている(2026-07-12).

    9 指標 + 基本情報 5 列 = 14 列は横スクロール必須になり見づらいため、
    表示指標をユーザーが選べるようにし、デフォルトは主要 4 指標のみ表示する.
    """
    at = _new_app()
    at.query_params["view"] = "ranking"
    at.run()
    assert not at.exception, f"ranking view で例外: {at.exception}"

    indicator_selector = at.multiselect(key="visible_indicators_current")
    assert len(indicator_selector.value) == 4, (
        f"デフォルト表示指標は 4 つのはずが {len(indicator_selector.value)} 個: "
        f"{indicator_selector.value}"
    )

    assert len(at.dataframe) >= 1, "ランキング表(dataframe)が描画されていない"
    columns = list(at.dataframe[0].value.columns)
    # 基本情報 5 列 + 選択指標 4 列 = 9 列(14 列から削減できている)
    assert len(columns) == 9, f"列数が 9 のはずが {len(columns)}: {columns}"
    for base_col in ("順位", "★", "総合偏差値", "都道府県", "地方"):
        assert base_col in columns, f"基本列 {base_col} が見当たらない"


def test_ranking_view_indicator_selection_can_be_widened() -> None:
    """指標選択を増やすと、表の列数もそれに応じて増える(絞り込みが実際に効いている)."""
    at = _new_app()
    at.query_params["view"] = "ranking"
    at.run()

    all_options = at.multiselect(key="visible_indicators_current").options
    at.multiselect(key="visible_indicators_current").set_value(all_options).run()

    assert not at.exception, f"全指標選択時に例外: {at.exception}"
    columns = list(at.dataframe[0].value.columns)
    # 基本情報 5 列 + 全 9 指標 = 14 列
    assert len(columns) == 14, f"全指標選択時は 14 列のはずが {len(columns)}: {columns}"


def test_map_view_defaults_to_all_prefectures_labeled() -> None:
    """Map: ラベル表示のデフォルトが「47都道府県すべて表示」になっている(2026-07-12).

    以前は上位/下位5県のみ表示で「値が読めない」UX 課題があったため変更.
    """
    at = _new_app()
    at.query_params["view"] = "map"
    at.run()
    assert not at.exception, f"map view で例外: {at.exception}"

    radio = at.radio(key="annotation_price_index_current")
    assert radio.value == "47都道府県すべて表示", (
        f"ラベル表示のデフォルトが想定と異なる: {radio.value}"
    )


def test_map_view_shows_region_cluster_summary() -> None:
    """Map: 地方別平均サマリー(8ブロック)が描画される(2026-07-12、地理的クラスタ視認).

    Map 画面固有のジョブ(空間的パターン認識)を担保する新機能.
    """
    at = _new_app()
    at.query_params["view"] = "map"
    at.run()
    assert not at.exception, f"map view で例外: {at.exception}"

    metrics = at.metric
    assert len(metrics) == 8, f"地方は 8 ブロックのはずが {len(metrics)} 件: {[m.label for m in metrics]}"
    expected_regions = {"北海道", "東北", "関東", "中部", "近畿", "中国", "四国", "九州・沖縄"}
    labeled_regions = {m.label.split(" ")[-1] for m in metrics}
    assert labeled_regions == expected_regions, (
        f"地方名が一致しない: {labeled_regions} != {expected_regions}"
    )


def test_map_view_secondary_controls_are_collapsed_in_expander() -> None:
    """Map: 主要都市・非日常スポット等の詳細設定が expander に畳まれている(2026-07-12、認知負荷軽減)."""
    at = _new_app()
    at.query_params["view"] = "map"
    at.run()
    assert not at.exception, f"map view で例外: {at.exception}"

    expander_labels = [e.label for e in at.expander if hasattr(e, "label")]
    assert any("詳細設定" in lbl for lbl in expander_labels), (
        f"「詳細設定」expander が見つからない: {expander_labels}"
    )
    # 主要都市マーカーのチェックボックスは expander 内でも動作する(デフォルト ON)
    checkbox = at.checkbox(key="major_cities_price_index_current")
    assert checkbox.value is True
