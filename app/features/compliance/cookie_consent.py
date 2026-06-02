"""Cookie 同意バナー — INV-BIZ-007(DEC-016 派生)を担保する.

DEC-016(2026-05-30 mode C 公開)+ GA4 解析導入時、利用者の事前同意を
取得してから Cookie を発火させる(オプトイン方式).

ポリシー整合:
    outputs/legal/privacy_policy.md §5.3 で「同意バナー → オプトイン」を
    明示しているため、本ファイルがその実装責務を持つ.

INV-BIZ-007: mode C 公開時 + Cookie/解析導入時、Cookie 同意バナーを表示しなければならない
"""

from __future__ import annotations

import streamlit as st

SESSION_KEY = "movemap_ga_consent"  # True / False / 未設定(=未判断)

PRIVACY_POLICY_URL = (
    "https://github.com/takanorikoyama-dev/MoveMap/"
    "blob/training/outputs/legal/privacy_policy.md"
)


def has_consented() -> bool:
    """同意済みか. 未判断 / 拒否なら False.

    Returns:
        True: 同意済み(GA4 を inject すべき)
        False: 拒否 or 未判断(GA4 は inject しない)
    """
    return bool(st.session_state.get(SESSION_KEY))


def render_consent_banner(measurement_id: str | None) -> bool:
    """Cookie 同意バナーを表示し、同意/拒否の状態を返す.

    Args:
        measurement_id: GA4 Measurement ID. None なら GA4 未設定で
            バナーも不要(False を返す).

    Returns:
        True: 同意済み → 呼び出し側で GA4 を有効化
        False: 拒否 / 未判断 → GA4 は無効

    UI 動作:
        - measurement_id が無い → バナー出さず False
        - 同意済み → バナー出さず True
        - 拒否済み → バナー出さず False
        - 未判断 → バナー表示 + ボタン待ち, False
    """
    if not measurement_id:
        return False  # GA4 未設定 → バナー不要

    consent = st.session_state.get(SESSION_KEY)
    if consent is True:
        return True
    if consent is False:
        return False  # 拒否済み → 再表示しない

    # 未判断 → バナー表示
    st.info(
        "🍪 **Cookie 利用のお知らせ**\n\n"
        "本サイトでは Google Analytics を用いてアクセス解析を行います。"
        "個人を特定する情報は取得しません(IP アドレスは匿名化)。"
        f" 詳細は [プライバシーポリシー]({PRIVACY_POLICY_URL}) をご覧ください。"
    )
    c1, c2, _ = st.columns([1, 1, 4])
    with c1:
        if st.button("同意する", key="ga_consent_yes", type="primary"):
            st.session_state[SESSION_KEY] = True
            st.rerun()
    with c2:
        if st.button("拒否する", key="ga_consent_no"):
            st.session_state[SESSION_KEY] = False
            st.rerun()
    return False


__all__ = ["has_consented", "render_consent_banner", "SESSION_KEY"]
