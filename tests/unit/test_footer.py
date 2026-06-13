"""フッターの単体テスト.

参照:
    - INV-BIZ-008(DEC-016 派生): mode C 公開時の法務リンク導線
    - DEC-017(2026-06-13): 法務リンクをサイト内 view 化、GitHub リポジトリリンク削除
"""

from __future__ import annotations

from app.features.compliance import footer


def test_footer_render_callable() -> None:
    """render() が import 可能で呼び出せる."""
    assert callable(footer.render)


def test_footer_constants_point_to_internal_views() -> None:
    """法務リンクがサイト内 view を指していること(DEC-017、INV-BIZ-008 の導線提供は維持)."""
    assert footer.TERMS_URL == "?view=terms"
    assert footer.PRIVACY_URL == "?view=privacy"
    assert footer.ISSUES_URL == "?view=contact"


def test_footer_no_longer_exposes_github_repo_url() -> None:
    """DEC-017: GitHub リポジトリリンクはフッターから削除されている."""
    assert not hasattr(footer, "REPO_URL"), (
        "REPO_URL は DEC-017 で削除。README 等から GitHub に到達してください。"
    )


def test_footer_metadata_complete() -> None:
    """運営者・最終改定日が定義されている(個人特定回避のためジェネリック化済)."""
    assert "MoveMap" in footer.OPERATOR_NAME
    # 最終改定日は YYYY-MM-DD 形式
    assert len(footer.LAST_UPDATED) == 10
    assert footer.LAST_UPDATED.count("-") == 2
