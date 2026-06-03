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


def _new_app() -> "AppTest":
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
