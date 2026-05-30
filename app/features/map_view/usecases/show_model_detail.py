"""SF-005 ShowModelDetail — AI モデルの根拠ページ.

参照: outputs/06_system_design/05_画面設計.md (SCR-003)
"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from app.features.map_view._cache import cached_latest_model_for
from app.features.map_view.dummy import PREDICTABLE_INDICATORS, dummy_value
from app.features.map_view.usecases.switch_indicator import INDICATOR_LABELS


def show_model_detail(indicator_id: str) -> None:
    """指定指標の予測モデル詳細を表示する."""
    if indicator_id not in PREDICTABLE_INDICATORS:
        st.warning(f"{INDICATOR_LABELS.get(indicator_id, indicator_id)} は予測対象外の指標です。")
        return

    label = INDICATOR_LABELS[indicator_id]
    st.subheader(f"AI 予測モデル詳細: {label}")

    info = cached_latest_model_for(indicator_id)

    # 取得元の透明性表示
    if info.availability.source == "db":
        ts = info.trained_at.strftime("%Y-%m-%d %H:%M") if info.trained_at else "—"
        st.caption(f"🔵 DB 実モデル表示中 / 学習日時: {ts}")
    else:
        note = info.availability.note or "DB に学習済モデルなし"
        st.caption(f"🟡 ダミーモデル表示中({note})")

    # モデル情報
    period = info.evaluation_period or {}
    period_text = f"{period.get('from', '?')} 〜 {period.get('to', '?')}" if period else "—"
    features = info.features_used or []

    st.markdown(f"- **使用モデル**: {info.model_type or '—'}")
    st.markdown(f"- **学習日時**: {info.trained_at.strftime('%Y-%m-%d %H:%M') if info.trained_at else 'ダミー(未学習)'}")
    st.markdown(f"- **評価期間**: {period_text}")
    st.markdown(f"- **R²**: {f'{info.r_squared:.3f}' if info.r_squared is not None else '—'}")
    st.markdown(f"- **MAE**: {f'{info.mae:.3f}' if info.mae is not None else '—'}")
    st.markdown(f"- **使用変数**: {', '.join(features) if features else '—'}")

    # 過去予測 vs 実測グラフ(ダミー表示は維持)
    months = [f"2024-{m:02d}" for m in range(1, 13)]
    actual_base = dummy_value(indicator_id, "13", "current") or 100.0
    actual = [actual_base + (i - 6) * 0.1 for i in range(12)]
    predicted = [v + 0.5 for v in actual]
    df = pd.DataFrame({"月": months, "実測": actual, "予測": predicted})

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df["月"], y=df["実測"], mode="lines+markers", name="実測"))
    fig.add_trace(go.Scatter(x=df["月"], y=df["予測"], mode="lines+markers", name="予測"))
    fig.update_layout(title=f"{label}: 過去予測 vs 実測(東京都・参考表示)", height=400)
    st.plotly_chart(fig, use_container_width=True)

    st.warning(
        "⚠️ 本予測は統計的推定であり、将来を保証するものではありません。"
        "投資判断にはご自身の責任にて複数情報を参照してください。"
    )
