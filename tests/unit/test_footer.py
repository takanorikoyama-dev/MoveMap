"""フッターの単体テスト.

参照:
    - INV-BIZ-008(DEC-016 派生): mode C 公開時の法務リンク導線
"""

from __future__ import annotations

from app.features.compliance import footer


def test_footer_render_callable() -> None:
    """render() が import 可能で呼び出せる."""
    assert callable(footer.render)


def test_footer_constants_contain_required_urls() -> None:
    """利用規約・プライバシーポリシーへのリンク URL が定義されている(INV-BIZ-008)."""
    assert "terms.md" in footer.TERMS_URL
    assert "privacy_policy.md" in footer.PRIVACY_URL
    assert footer.REPO_URL.startswith("https://github.com/")
    assert "/issues" in footer.ISSUES_URL


def test_footer_metadata_complete() -> None:
    """運営者・最終改定日が定義されている."""
    assert "神山隆憲" in footer.OPERATOR_NAME
    # 最終改定日は YYYY-MM-DD 形式
    assert len(footer.LAST_UPDATED) == 10
    assert footer.LAST_UPDATED.count("-") == 2
