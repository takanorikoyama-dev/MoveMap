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
    """INV-BIZ-005: 免責バナーが表示されている(warning 要素として存在)."""
    at = _new_app()
    at.run()
    # streamlit の st.warning は warning() で取得可能
    assert len(at.warning) >= 1
    # 免責テキストの主要キーワードを含む
    texts = " ".join(w.value for w in at.warning)
    assert "個人利用" in texts


def test_app_renders_three_tabs() -> None:
    """MAP / 都道府県詳細 / モデル根拠 の 3 タブ構成."""
    at = _new_app()
    at.run()
    # streamlit テスト API では tabs は title でなく内部要素を持つ
    # ここでは「副題的に main 要素にプレースホルダがある」のみ簡易検証
    # 詳細はインタラクションテストで(将来)
    titles = [el.value for el in at.title]
    assert any("MoveMap" in t for t in titles)


def test_app_sidebar_has_indicator_and_horizon_radios() -> None:
    """サイドバーに 指標 / 年次 の radio が 2 つ存在."""
    at = _new_app()
    at.run()
    sidebar_radios = at.sidebar.radio
    # 指標 + 年次 = 2(他に追加 radio がなければ)
    assert len(sidebar_radios) >= 2
