"""SF-020 免責表示 — INV-BIZ-005 を担保する常時表示コンポーネント."""

from __future__ import annotations

import streamlit as st

DISCLAIMER_TEXT = (
    "⚠️ 本ツールは**個人利用を目的とした参考情報**です。"
    "投資判断・意思決定の最終責任はユーザーにあります。"
    "予測値は統計的推定であり、将来を保証するものではありません。"
)


def render() -> None:
    """全画面で常時表示する免責バナー(INV-BIZ-005)."""
    st.warning(DISCLAIMER_TEXT)
