"""サイドバー用のデータ状態サマリパネル.

main.py から呼び出し、ユーザーに「いま見ているデータが何ベースか」を伝える.
"""

from __future__ import annotations

import streamlit as st

from app.features.map_view.data_status import HealthSummary


@st.cache_data(ttl=60)  # 1 分キャッシュ(頻繁な DB クエリを避ける)
def _cached_health() -> HealthSummary:
    from app.features.map_view.data_status import collect_health

    return collect_health()


def render_status_panel() -> None:
    """サイドバーにデータ状態サマリを表示."""
    summary = _cached_health()
    st.sidebar.markdown("---")
    st.sidebar.subheader("データ状態")

    if not summary.db_exists:
        st.sidebar.warning("📂 DB 未生成")
        st.sidebar.caption("`python scripts/seed.py --with-synthetic-history` を実行してください")
        return

    if summary.has_current_data:
        st.sidebar.success("🔵 実データ(現在値)あり")
    else:
        st.sidebar.info("🟡 現在値はダミー(`run_batch.py` で取込)")

    if summary.has_predictions:
        st.sidebar.success("🔵 AI 予測モデルあり")
    else:
        st.sidebar.info("🟡 予測モデル未学習")

    batch = summary.latest_batch
    if batch and batch.status:
        ts = batch.ended_at.strftime("%Y-%m-%d %H:%M") if batch.ended_at else "—"
        icon = {"success": "✅", "partial": "⚠️", "failure": "❌", "running": "⏳"}.get(batch.status, "❓")
        st.sidebar.caption(f"{icon} 最新バッチ: **{batch.status}** ({ts})")
    else:
        st.sidebar.caption("ℹ️ バッチ未実行")

    if summary.error_count_last_7days > 0:
        st.sidebar.warning(f"⚠️ 直近 7 日のエラー: {summary.error_count_last_7days} 件")
