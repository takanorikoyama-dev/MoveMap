"""フッター — INV-BIZ-008(DEC-016 派生)を担保する法務リンク導線.

DEC-016(2026-05-30 mode C 解禁)に伴い、UI フッターに以下を常設表示する:
    - 利用規約へのリンク(サイト内 view)
    - プライバシーポリシーへのリンク(サイト内 view)
    - お問い合わせへのリンク(サイト内 view)
    - 運営者・最終改定日表記
    - 画像クレジット総合表記(Unsplash + Wikimedia)

DEC-017(2026-06-13)で表示形態を変更:
    - 旧: 利用規約 / プライバシー → GitHub の blob/training/outputs/legal/*.md を新タブで開く
    - 新: サイト内 view(?view=terms / ?view=privacy / ?view=contact)に遷移
    - 旧: GitHub リポジトリリンクをフッターに表示
    - 新: 削除(ポートフォリオ訪問者の UX を優先、技術者層は README 等から到達可能)

INV-BIZ-008: mode C 公開時、UI フッターから利用規約・プライバシーポリシーへの導線を必ず提供
    → 本変更後も導線は維持(リンク先がサイト内に変わるだけで、要件は満たす)
"""

from __future__ import annotations

import streamlit as st

from app.features.map_view.images import all_credits_summary

# 法務文書(outputs/legal/ 配下が正典)— サイト内 view として表示
# DEC-017(2026-06-13): GitHub URL からサイト内 query_params へ変更.
TERMS_URL = "?view=terms"
PRIVACY_URL = "?view=privacy"
ISSUES_URL = "?view=contact"
# REPO_URL は DEC-017 で削除(ポートフォリオ訪問者向けに UI ノイズを減らす).

OPERATOR_NAME = "MoveMap 開発者(個人制作)"
LAST_UPDATED = "2026-06-13"

FOOTER_CSS = """
<style>
.movemap-footer {
    margin-top: 2.5rem;
    padding: 1.5rem 1rem 1rem;
    border-top: 2px solid #e0e0e0;
    color: #444;
    font-size: 0.92rem;
    line-height: 1.7;
}
.movemap-footer a {
    color: #1976d2;
    text-decoration: underline;
    margin-right: 0.6rem;
}
.movemap-footer .movemap-footer-links {
    margin-bottom: 0.6rem;
}
.movemap-footer .movemap-footer-meta {
    color: #666;
    font-size: 0.86rem;
}
</style>
"""


def render() -> None:
    """法務リンク・運営者情報を常時表示するフッター(INV-BIZ-008)."""
    st.markdown(FOOTER_CSS, unsafe_allow_html=True)
    photo_credit_html = all_credits_summary()
    # Markdown のリンクを HTML <a> に簡易変換(footer は raw HTML 表示なので)
    if photo_credit_html:
        import re

        photo_credit_html = re.sub(
            r"\[([^\]]+)\]\(([^)]+)\)",
            r'<a href="\2" target="_blank">\1</a>',
            photo_credit_html,
        )
        photo_credit_html = f"<br>{photo_credit_html}"
    # サイト内 view への遷移は target を指定しない(同窓内で query_params 切替).
    st.markdown(
        f"""
<div class="movemap-footer" id="footer-legal">
  <div class="movemap-footer-links">
    📋 <a href="{TERMS_URL}" id="footer-legal-terms">利用規約</a>
    🔒 <a href="{PRIVACY_URL}" id="footer-legal-privacy">プライバシーポリシー</a>
    💬 <a href="{ISSUES_URL}" id="footer-legal-contact">お問い合わせ</a>
  </div>
  <div class="movemap-footer-meta">
    MoveMap — 地方移住MAP(個人制作のポートフォリオ、商用ではありません)<br>
    運営者: {OPERATOR_NAME} / 最終改定日: {LAST_UPDATED}<br>
    本ツールは投資助言・不動産取引助言・移住助言ではありません。詳細は利用規約をご確認ください。{photo_credit_html}
  </div>
</div>
""",
        unsafe_allow_html=True,
    )
