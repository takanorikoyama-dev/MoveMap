"""SF-020 ShowDisclaimer の単体テスト.

参照:
    - INV-BIZ-005: 免責バナー常時表示
    - INV-BIZ-006(DEC-016 派生): mode C 公開時の投資/移住助言ではない明示
"""

from __future__ import annotations

from app.features.compliance.disclaimer import (
    DETAILED_DISCLAIMER_MARKDOWN,
    DISCLAIMER_TEXT,
)


def test_disclaimer_text_contains_required_phrases() -> None:
    """短文免責に必須要素(参考情報/予測値の限界)が含まれる(INV-BIZ-005)."""
    assert "参考情報" in DISCLAIMER_TEXT
    assert "予測" in DISCLAIMER_TEXT
    assert "保証" in DISCLAIMER_TEXT


def test_disclaimer_text_includes_three_advice_disclaimers() -> None:
    """短文免責に「投資/不動産取引/移住の助言ではない」明示(INV-BIZ-006)."""
    assert "投資助言" in DISCLAIMER_TEXT
    assert "不動産取引助言" in DISCLAIMER_TEXT
    assert "移住助言" in DISCLAIMER_TEXT


def test_detailed_disclaimer_covers_r03_legal_points() -> None:
    """詳細免責に R-03 の 3 法令観点が含まれる(DEC-016 対応)."""
    assert "不動産公正競争規約" in DETAILED_DISCLAIMER_MARKDOWN
    assert "金融商品取引法" in DETAILED_DISCLAIMER_MARKDOWN
    assert "移住" in DETAILED_DISCLAIMER_MARKDOWN


def test_disclaimer_render_callable() -> None:
    """render() が import 可能で呼び出せる(Streamlit ランタイムは smoke で別途検証)."""
    from app.features.compliance import disclaimer

    assert callable(disclaimer.render)
