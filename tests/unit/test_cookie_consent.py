"""Cookie 同意バナーの単体テスト.

参照:
    - INV-BIZ-007(DEC-016 派生): mode C + Cookie/解析導入時のオプトイン
    - outputs/legal/privacy_policy.md §5.3
"""

from __future__ import annotations

import streamlit as st

from app.features.compliance import cookie_consent as cc


def _clear_state() -> None:
    """テスト独立性のため session_state をクリア."""
    if hasattr(st, "session_state"):
        try:
            if cc.SESSION_KEY in st.session_state:
                del st.session_state[cc.SESSION_KEY]
        except Exception:  # noqa: BLE001
            pass


def test_render_returns_false_when_ga4_not_configured() -> None:
    """GA4 未設定なら同意フローが走らない(バナーも出さない)."""
    _clear_state()
    assert cc.render_consent_banner(None) is False
    assert cc.render_consent_banner("") is False


def test_render_returns_true_when_already_consented() -> None:
    _clear_state()
    st.session_state[cc.SESSION_KEY] = True
    assert cc.render_consent_banner("G-XXXXXXXXXX") is True


def test_render_returns_false_when_already_declined() -> None:
    _clear_state()
    st.session_state[cc.SESSION_KEY] = False
    assert cc.render_consent_banner("G-XXXXXXXXXX") is False


def test_has_consented_reflects_session_state() -> None:
    _clear_state()
    assert cc.has_consented() is False
    st.session_state[cc.SESSION_KEY] = True
    assert cc.has_consented() is True
    st.session_state[cc.SESSION_KEY] = False
    assert cc.has_consented() is False


def test_module_exports_session_key() -> None:
    assert cc.SESSION_KEY == "movemap_ga_consent"
