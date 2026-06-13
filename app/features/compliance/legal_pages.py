"""法務関連のサイト内ページ (terms / privacy / contact).

DEC-017(2026-06-13): フッターの法務リンクを GitHub の raw markdown ではなく
サイト内 view として表示する形に変更. INV-BIZ-008(導線提供)は維持しつつ、
ポートフォリオ訪問者の UX を改善する.

利用規約とプライバシーポリシーは正典の `outputs/legal/*.md` を読み込んで
そのまま st.markdown で表示する(正典は変更しない).
お問い合わせは inline で記述(問い合わせ手段の案内).
"""

from __future__ import annotations

from pathlib import Path

import streamlit as st

# repo root: app/features/compliance/legal_pages.py から見て 3 階層上
_REPO_ROOT = Path(__file__).resolve().parents[3]
_TERMS_MD = _REPO_ROOT / "outputs" / "legal" / "terms.md"
_PRIVACY_MD = _REPO_ROOT / "outputs" / "legal" / "privacy_policy.md"


def _read_markdown(path: Path, fallback_title: str) -> str:
    """正典の Markdown を読み込む. 失敗時はフォールバック文言."""
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        # Streamlit Cloud で何らかの理由で読めなかった場合
        return (
            f"# {fallback_title}\n\n"
            "現在ドキュメントを読み込めませんでした。"
            "お手数ですが、GitHub リポジトリの `outputs/legal/` をご参照ください。\n"
        )


def show_terms() -> None:
    """利用規約のサイト内表示."""
    st.markdown(_read_markdown(_TERMS_MD, "利用規約"))


def show_privacy() -> None:
    """プライバシーポリシーのサイト内表示."""
    st.markdown(_read_markdown(_PRIVACY_MD, "プライバシーポリシー"))


def show_contact() -> None:
    """お問い合わせページ(inline). 個人制作のため正式問い合わせ窓口は GitHub Issue."""
    st.markdown(
        """# お問い合わせ

MoveMap は個人制作のポートフォリオ作品です。
正式な問い合わせ窓口は **GitHub Issue** にて受け付けています。

## ご連絡方法

### 1. GitHub Issue(推奨)

不具合報告・機能リクエスト・データ誤りの指摘などは GitHub Issue にて受付しています。

🔗 **[GitHub Issue を作成する](https://github.com/takanorikoyama-dev/MoveMap/issues/new)**

GitHub アカウントが必要です(無料で取得可能)。

### 2. 個別のご相談

ご相談内容によっては、対応に **数日〜数週間** お時間をいただく場合があります。
個人制作のため、24/7 のサポートは提供しておりません。あらかじめご了承ください。

## よくあるご質問

| Q | A |
|---|---|
| **データはどこから?** | 公的統計(総務省・国土交通省・e-Stat・気象庁・警察庁等)を機械的に収集しています。詳細は [利用規約](?view=terms) §4 をご参照ください。 |
| **投資・移住助言として使えますか?** | **いいえ**。本ツールは公的統計の機械的延長であり、投資・不動産取引・移住の助言ではありません(INV-BIZ-006)。 |
| **個人情報は収集されますか?** | Cookie 同意済の場合のみ Google Analytics で匿名アクセスログを取得します。詳細は [プライバシーポリシー](?view=privacy) をご参照ください。 |
| **データの更新頻度は?** | 月次バッチで自動更新しています(指標により quarterly / yearly のものもあり)。 |

---

**運営者**: MoveMap 開発者(個人制作)
**最終更新**: 2026-06-13
"""
    )
