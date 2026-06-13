"""法務関連サイト内 view の単体テスト(DEC-017).

参照:
    - INV-BIZ-008: 法務文書への導線提供(リンク先がサイト内 view でも要件は満たす)
    - DEC-017: 法務リンクをサイト内 view 化、GitHub リポジトリリンク削除
"""

from __future__ import annotations

from app.features.compliance import legal_pages


def test_show_terms_callable() -> None:
    """show_terms() が import 可能で呼び出せる."""
    assert callable(legal_pages.show_terms)


def test_show_privacy_callable() -> None:
    """show_privacy() が import 可能で呼び出せる."""
    assert callable(legal_pages.show_privacy)


def test_show_contact_callable() -> None:
    """show_contact() が import 可能で呼び出せる."""
    assert callable(legal_pages.show_contact)


def test_legal_markdown_files_resolvable() -> None:
    """正典 Markdown のパスが repo root から正しく解決できる(物理ファイルが存在)."""
    assert legal_pages._TERMS_MD.exists(), (
        f"利用規約の正典が見つかりません: {legal_pages._TERMS_MD}"
    )
    assert legal_pages._PRIVACY_MD.exists(), (
        f"プライバシーポリシーの正典が見つかりません: {legal_pages._PRIVACY_MD}"
    )


def test_read_markdown_returns_content() -> None:
    """正典 Markdown を読み込めて、最低限の長さがある."""
    terms_text = legal_pages._read_markdown(legal_pages._TERMS_MD, "fallback")
    privacy_text = legal_pages._read_markdown(legal_pages._PRIVACY_MD, "fallback")
    # 最低 200 文字以上(正典が実質的に存在することの確認)
    assert len(terms_text) > 200
    assert len(privacy_text) > 200


def test_read_markdown_fallback_on_missing_file(tmp_path) -> None:
    """ファイルが存在しない場合はフォールバック文言を返す."""
    missing = tmp_path / "does_not_exist.md"
    result = legal_pages._read_markdown(missing, "テストタイトル")
    assert "テストタイトル" in result
    assert "GitHub" in result  # フォールバック案内が含まれる
