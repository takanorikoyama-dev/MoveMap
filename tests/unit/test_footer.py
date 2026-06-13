"""フッターの単体テスト.

参照:
    - INV-BIZ-008(DEC-016 派生): mode C 公開時の法務リンク導線
    - DEC-017(2026-06-13): 法務リンクをサイト内 view 化、GitHub リポジトリリンク削除
    - DEC-018(2026-06-13): 全クレジット導線(image_credits.md)をフッターから削除
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


def test_footer_does_not_import_all_credits_summary() -> None:
    """DEC-018: フッターは全クレジット導線を削除したため、画像クレジット API への依存も解除されている.

    個別画像近くの Photo: クレジット表記(hero / prefecture_detail)は維持される.
    """
    import inspect

    source = inspect.getsource(footer)
    assert "all_credits_summary" not in source, (
        "DEC-018 で全クレジット導線を削除済み。"
        "footer から all_credits_summary を呼び出してはならない。"
    )
    assert "image_credits.md" not in source, (
        "DEC-018 で image_credits.md への直接リンクは削除済み。"
    )
