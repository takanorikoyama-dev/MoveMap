"""Streamlit 標準 UI クローム(メニュー・フッター・ツールバー)の非表示化の単体テスト.

2026-07-12: リスティング広告配信に伴い、広告経由の訪問者に「無料 OSS の個人アプリ」
という印象を与えないよう、Fork ボタン・GitHub アイコン・ハンバーガーメニューを隠す
対応を行った. この非表示化 CSS が _GLOBAL_CSS から欠落しないことを担保する.
"""

from __future__ import annotations

from app.shared import ui_theme


def test_global_css_hides_main_menu() -> None:
    """ハンバーガーメニュー(⋮: Settings/Print/Record/About)を非表示にする CSS がある."""
    assert "#MainMenu" in ui_theme._GLOBAL_CSS
    assert "visibility: hidden" in ui_theme._GLOBAL_CSS


def test_global_css_hides_footer() -> None:
    """「Made with Streamlit」フッターを非表示にする CSS がある."""
    assert "footer { visibility: hidden; }" in ui_theme._GLOBAL_CSS


def test_global_css_hides_toolbar() -> None:
    """Streamlit Cloud のツールバー(Fork/GitHub/Manage app)を隠す CSS がある."""
    assert 'data-testid="stToolbar"' in ui_theme._GLOBAL_CSS
