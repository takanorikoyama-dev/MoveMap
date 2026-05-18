"""SF-020 ShowDisclaimer の単体テスト.

参照: INV-BIZ-005 免責バナー常時表示
"""

from __future__ import annotations

from app.features.compliance.disclaimer import DISCLAIMER_TEXT


def test_disclaimer_text_contains_required_phrases() -> None:
    """免責テキストに必須要素(個人利用/投資判断/予測値)が含まれる."""
    assert "個人利用" in DISCLAIMER_TEXT
    assert "投資判断" in DISCLAIMER_TEXT
    assert "予測" in DISCLAIMER_TEXT


def test_disclaimer_render_callable() -> None:
    """render() が import 可能で呼び出せる(Streamlit ランタイムは smoke で別途検証)."""
    from app.features.compliance import disclaimer

    assert callable(disclaimer.render)
