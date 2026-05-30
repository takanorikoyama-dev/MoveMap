"""Streamlit エントリポイント.

UI/UX 設計(2026-05-20 強化):
    - 50-60 代向けに基本フォント大、行間広め、ボタンタップ領域確保
    - ヒーローバナーで「何ができるアプリか」を即座に伝達
    - 各タブ冒頭にステップガイド(このタブで何ができるか/次に何を見るか)
    - 印刷モード切替(サイドバー隠し、A4 1 枚に収まるレイアウト)
"""

from __future__ import annotations

import streamlit as st

from app.features.compliance.disclaimer import render as render_disclaimer
from app.features.compliance.show_data_sources import show_data_sources
from app.features.map_view.components.status_panel import render_status_panel
from app.features.map_view.usecases.show_comparison import show_comparison
from app.features.map_view.usecases.show_diagnosis import show_diagnosis
from app.features.map_view.usecases.show_map import show_map
from app.features.map_view.usecases.show_model_detail import show_model_detail
from app.features.map_view.usecases.show_prefecture_detail import (
    PREFECTURE_NAMES,
    show_prefecture_detail,
)
from app.features.map_view.usecases.show_ranking import show_ranking
from app.features.map_view.usecases.switch_horizon import HORIZON_LABELS, switch_horizon
from app.features.map_view.usecases.switch_indicator import (
    INDICATOR_LABELS,
    labeled as indicator_labeled,
    switch_indicator,
)
from app.shared.config import load_config
from app.shared.ui_theme import (
    inject_ga4,
    inject_global_css,
    render_current_band,
    render_hero,
    render_mobile_hint,
    render_tab_guide,
)

st.set_page_config(
    page_title="MoveMap — 地方移住MAP",
    page_icon="🗾",
    layout="wide",
    initial_sidebar_state="expanded",
)

# グローバル CSS(可読性 + 印刷モード)を最初に注入
inject_global_css()
# GA4 トラッキング(Measurement ID が .env に設定されているときだけ有効化)
inject_ga4(load_config().ga4_measurement_id)

st.title("MoveMap — 地方移住MAP")
render_hero()
render_mobile_hint()
render_disclaimer()

# --- URL query → セッション初期値 反映(共有用) ---
_qp = st.query_params
if "indicator" in _qp and "selected_indicator_label" not in st.session_state:
    qid = _qp.get("indicator")
    qlabel = INDICATOR_LABELS.get(qid)  # type: ignore[arg-type]
    if qlabel:
        # サイドバーラジオは絵文字付きラベルになっているため、組み立て直す
        from app.features.map_view.usecases.switch_indicator import labeled as _labeled
        st.session_state["selected_indicator_label"] = _labeled(qid)  # type: ignore[arg-type]
if "horizon" in _qp and "selected_horizon_label" not in st.session_state:
    qh = _qp.get("horizon")
    qhlabel = HORIZON_LABELS.get(qh)  # type: ignore[arg-type]
    if qhlabel:
        st.session_state["selected_horizon_label"] = qhlabel

indicator_id = switch_indicator()
horizon = switch_horizon()

# 選択を URL に反映(再アクセス時に同じ状態を復元できる)
st.query_params["indicator"] = indicator_id
st.query_params["horizon"] = horizon

st.sidebar.markdown("---")
st.sidebar.caption(
    f"選択中: **{indicator_labeled(indicator_id)}** / **{HORIZON_LABELS[horizon]}**"
)
st.sidebar.caption(
    "🔗 このページの URL をコピーすれば、同じ選択状態で開けます(指標・年次が URL に反映)"
)

# 画面上部に「現在の選択」を大きく表示(スマホでサイドバーが隠れていても何を見ているか分かる)
render_current_band(indicator_labeled(indicator_id), HORIZON_LABELS[horizon])

# 印刷モードトグル(サイドバー下部)
st.sidebar.markdown("---")
print_mode = st.sidebar.checkbox(
    "🖨️ 印刷用ビュー",
    value=False,
    key="print_mode",
    help="チェックするとサイドバー/タブを隠した印刷向けレイアウトになります。ブラウザの印刷(Ctrl+P)と併用してください。",
)
if print_mode:
    st.markdown(
        """
        <style>
        [data-testid="stSidebar"] { display: none !important; }
        button[data-baseweb="tab"] { display: none !important; }
        [data-testid="stTabs"] [data-baseweb="tab-list"] { display: none !important; }
        .stApp { background: white !important; }
        </style>
        """,
        unsafe_allow_html=True,
    )

# データ状態パネル(運用透明性)
render_status_panel()

tab_diagnosis, tab_map, tab_ranking, tab_compare, tab_detail, tab_model = st.tabs(
    ["🎯 診断", "🗾 地図", "🏆 順位", "⚔️ 比較", "📍 詳細", "🤖 AI根拠"]
)

with tab_diagnosis:
    render_tab_guide(
        "<strong>このタブから始めるのがおすすめです。</strong> "
        "5 つの簡単な質問に答えるだけで、あなたに合う <strong>移住先 3 県</strong> をご提案します。"
        "<br>診断結果は「🏆 ランキング」タブの重み付けスライダーにも自動反映されます。"
    )
    show_diagnosis(horizon)

with tab_map:
    render_tab_guide(
        "<strong>このタブでできること:</strong> "
        f"選んだ観点(現在: {indicator_labeled(indicator_id)})で 47 都道府県を地図上に色分け表示します。"
        "緑が濃いほど住みやすい県です。"
        "<br><strong>次のおすすめ:</strong> 「🏆 ランキング」タブで重み付けして自分の優先度に合った順位を見る → "
        "「⚔️ 2県比較」タブで気になる 2 県を並べてレーダーで比較。"
    )
    show_map(indicator_id, horizon)

with tab_ranking:
    render_tab_guide(
        "<strong>このタブでできること:</strong> "
        "7 つの観点をあなたの優先度で重み付けし、47 都道府県を住みやすさ総合スコア順に並べます。"
        "<br><strong>使い方:</strong> ⚖️ スライダー → 重要視する観点ほど大きく、興味がない観点は 0 に。"
        "📌 ピン留めで気になる県を上部に固定、📥 CSV ダウンロードで家族と共有できます。"
    )
    show_ranking(horizon)

with tab_compare:
    render_tab_guide(
        "<strong>このタブでできること:</strong> "
        "都道府県を 2 つ選んで、7 観点の偏差値プロファイルをレーダーチャートで重ね表示します。"
        "外側に広いほど住みやすい県です。"
    )
    show_comparison(horizon)

with tab_detail:
    render_tab_guide(
        "<strong>このタブでできること:</strong> "
        "1 都道府県を選んで、7 観点の最新値+ AI 予測(3 年後/5 年後/10 年後)をまとめて確認できます。"
    )
    pref_options = [f"{code} {name}" for code, name in PREFECTURE_NAMES.items()]
    chosen = st.selectbox(
        "都道府県を選択",
        options=pref_options,
        index=12,  # default: 東京都
        key="selected_prefecture",
    )
    chosen_code = chosen.split(" ", 1)[0]
    show_prefecture_detail(chosen_code)

with tab_model:
    render_tab_guide(
        "<strong>このタブでできること:</strong> "
        "AI 予測モデル(ARIMA + Prophet)の精度(R²)や学習データの透明性を確認できます。"
        "予測値を判断材料にする前にここを見ると安心です。"
    )
    show_model_detail(indicator_id)

st.markdown("---")
show_data_sources(None)
