"""SF-021 ShowDataSources — 指標のデータ出典・最終更新日を表示."""

from __future__ import annotations

import duckdb
import streamlit as st


def show_data_sources(con: duckdb.DuckDBPyConnection, indicator_id: str | None = None) -> None:
    """データ出典バッジを表示する.

    Args:
        con: DuckDB 接続.
        indicator_id: 特定指標(None なら全ソース一覧).

    Raises:
        NotImplementedError: 本体未実装.
    """
    if indicator_id is None:
        st.caption("出典: e-Stat / 国交省地価公示 / 不動産価格指数 / 環境省そらまめくん / 国土地理院 ハザードマップポータル / 国交省 交通インフラ")
        return
    raise NotImplementedError("Phase 7 続セッションで実装(指標別出典 + 最終更新日)")
