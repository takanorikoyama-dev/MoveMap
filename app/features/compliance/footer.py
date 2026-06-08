"""フッター — INV-BIZ-008(DEC-016 派生)を担保する法務リンク導線.

DEC-016(2026-05-30 mode C 解禁)に伴い、UI フッターに以下を常設表示する:
    - 利用規約へのリンク(outputs/legal/terms.md の要旨)
    - プライバシーポリシーへのリンク(outputs/legal/privacy_policy.md の要旨)
    - GitHub リポジトリリンク(お問い合わせ窓口)
    - 運営者・最終改定日表記
    - 画像クレジット総合表記(Unsplash + Wikimedia)

INV-BIZ-008: mode C 公開時、UI フッターから利用規約・プライバシーポリシーへの導線を必ず提供
"""

from __future__ import annotations

import streamlit as st

from app.features.map_view.images import all_credits_summary

# 法務文書(outputs/legal/ 配下の正典)— GitHub training ブランチ上で公開閲覧可能
TERMS_URL = "https://github.com/takanorikoyama-dev/MoveMap/blob/training/outputs/legal/terms.md"
PRIVACY_URL = "https://github.com/takanorikoyama-dev/MoveMap/blob/training/outputs/legal/privacy_policy.md"
REPO_URL = "https://github.com/takanorikoyama-dev/MoveMap"
ISSUES_URL = "https://github.com/takanorikoyama-dev/MoveMap/issues"

OPERATOR_NAME = "MoveMap 開発者(個人制作)"
LAST_UPDATED = "2026-05-30"

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
    st.markdown(
        f"""
<div class="movemap-footer" id="footer-legal">
  <div class="movemap-footer-links">
    📋 <a href="{TERMS_URL}" target="_blank" id="footer-legal-terms">利用規約</a>
    🔒 <a href="{PRIVACY_URL}" target="_blank" id="footer-legal-privacy">プライバシーポリシー</a>
    🐙 <a href="{REPO_URL}" target="_blank">GitHub リポジトリ</a>
    💬 <a href="{ISSUES_URL}" target="_blank">お問い合わせ(GitHub Issue)</a>
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
