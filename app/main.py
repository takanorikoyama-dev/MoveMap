"""Streamlit エントリポイント.

UI 設計(2026-06-02 大幅刷新):
    - サイドバー廃止、全画面ワイドビジュアル
    - ホーム = ヒーロー(4 枚自動横スライド、海と自然テーマ)+ 6 セクションバナー
    - 各セクションは state-based でクリック後に切替
    - 各セクション画面に「← ホームに戻る」ボタン
    - 既存タブ構成(診断/地図/順位/比較/詳細/AI根拠)は、バナークリック型導線に変更
"""

from __future__ import annotations

import streamlit as st

from app.features.compliance.cookie_consent import render_consent_banner
from app.features.compliance.disclaimer import render as render_disclaimer
from app.features.compliance.footer import render as render_footer
from app.features.compliance.show_data_sources import show_data_sources
from app.features.map_view.usecases.show_comparison import show_comparison
from app.features.map_view.usecases.show_diagnosis import show_diagnosis
from app.features.map_view.usecases.show_map import show_map
from app.features.map_view.usecases.show_model_detail import show_model_detail
from app.features.map_view.usecases.show_prefecture_detail import (
    PREFECTURE_NAMES,
    show_prefecture_detail,
)
from app.features.map_view.usecases.show_ranking import show_ranking
from app.features.map_view.usecases.switch_horizon import HORIZON_LABELS
from app.features.map_view.usecases.switch_indicator import (
    INDICATOR_LABELS,
    labeled as indicator_labeled,
)
from app.shared.bootstrap import ensure_db_initialized
from app.shared.config import load_config
from app.shared.ui_theme import (
    SECTION_KEYS,
    inject_ga4,
    inject_global_css,
    render_back_to_home_button,
    render_hero,
    render_section_banners,
)

# ephemeral 環境(Streamlit Cloud)で DB が無ければ自動初期化
ensure_db_initialized()

st.set_page_config(
    page_title="MoveMap — 地方移住MAP",
    page_icon="🗾",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# グローバル CSS(サイドバー非表示 + ヒーロー + バナー定義含む)
inject_global_css()

# Cookie 同意バナー(INV-BIZ-007、GA4 設定時のみ) + GA4 注入(同意済みのみ)
_ga4_id = load_config().ga4_measurement_id
if render_consent_banner(_ga4_id):
    inject_ga4(_ga4_id)


# ====================================================
# View Router(session_state 主導、URL は補助同期)
# ====================================================
_VALID_VIEWS = ("home",) + SECTION_KEYS

# URL クエリ ?view=KEY を毎回 session_state に同期.
# ・?view=KEY (valid)            → KEY をアクティブに
# ・?view 不在 or 無効            → home(クリーン URL "/" を home として扱う)
# `<a href='?view=KEY'>` や `<a href='/'>` のような外部リンク遷移にも追従する.
_qp_view = st.query_params.get("view")
_target_view = _qp_view if _qp_view in _VALID_VIEWS else "home"
if st.session_state.get("active_view") != _target_view:
    st.session_state["active_view"] = _target_view


def _active_view() -> str:
    """現在表示中のビュー名."""
    return st.session_state.get("active_view", "home")


def _navigate(view: str) -> None:
    """view を変更してリラン.

    Streamlit の query_params 単独だと環境によっては反映が遅れるため、
    session_state を真の状態源にし、URL は補助同期だけ行う.
    ホーム遷移時は次回描画でブラウザを最上部へスクロールさせるフラグを立てる.
    """
    if view == "home":
        st.session_state["_scroll_to_top_pending"] = True
    st.session_state["active_view"] = view
    try:
        st.query_params["view"] = view
    except Exception:  # noqa: BLE001
        pass  # URL 同期失敗してもアプリは動作する
    st.rerun()


def _scroll_to_top_js() -> None:
    """ブラウザを最上部にスクロール(ヒーロー位置まで戻す).

    Streamlit は st.rerun() でスクロール位置を保持するため、
    ホーム遷移直後だけ JS でリセットする.
    """
    st.markdown(
        """<script>
        (function(){
          const scroll = () => {
            window.scrollTo({top:0, left:0, behavior:'instant'});
            if (document.documentElement) document.documentElement.scrollTop = 0;
            if (document.body) document.body.scrollTop = 0;
            if (window.parent && window.parent !== window) {
              try { window.parent.scrollTo({top:0, left:0, behavior:'instant'}); } catch(e){}
              try { window.parent.document.documentElement.scrollTop = 0; } catch(e){}
              try { window.parent.document.body.scrollTop = 0; } catch(e){}
            }
          };
          scroll();
          setTimeout(scroll, 50);
          setTimeout(scroll, 200);
        })();
        </script>""",
        unsafe_allow_html=True,
    )


# ====================================================
# ホーム画面
# ====================================================
if _active_view() == "home":
    # 直前にセクションから「ホームに戻る」をクリックした直後のみ最上部へ
    if st.session_state.pop("_scroll_to_top_pending", False):
        _scroll_to_top_js()
    render_hero()
    st.markdown("### コンテンツ")
    st.caption("見たいコンテンツを選んでください。各バナー下のボタンで該当画面へ移動します。")
    chosen = render_section_banners()
    if chosen:
        _navigate(chosen)

    # ホーム下部に免責(INV-BIZ-005/006)
    st.markdown("---")
    render_disclaimer()
    st.markdown("---")
    show_data_sources(None)

# ====================================================
# 各セクション画面
# ====================================================
else:
    # TOPページボタン(st.button + session_state 強制リセット方式).
    # link_button や <a href> 系は環境依存で動かないことがあるため、
    # 確実に動作する Streamlit ボタン + 内部 state 更新で実装.
    if render_back_to_home_button():
        # query_params 全消去で URL を "/" に
        for _k in list(st.query_params.keys()):
            try:
                del st.query_params[_k]
            except Exception:  # noqa: BLE001
                pass
        # session_state を強制的にホームに
        st.session_state["active_view"] = "home"
        st.session_state["_scroll_to_top_pending"] = True
        st.rerun()
    st.markdown("---")

    view = _active_view()

    # 診断 — indicator/horizon に依存しない
    if view == "diagnosis":
        show_diagnosis("current")

    # 地図 / 順位 / 比較 / 詳細 / AI根拠 — indicator/horizon が必要
    else:
        # インライン indicator + horizon セレクタ
        c1, c2 = st.columns(2)
        with c1:
            indicator_label = st.selectbox(
                "観点",
                options=[indicator_labeled(i) for i in INDICATOR_LABELS.keys()],
                index=0,
                key="inline_indicator_label",
            )
            indicator_id = next(
                (k for k in INDICATOR_LABELS if indicator_labeled(k) == indicator_label),
                "price_index",
            )
        with c2:
            horizon_label = st.selectbox(
                "時点",
                options=list(HORIZON_LABELS.values()),
                index=0,
                key="inline_horizon_label",
            )
            horizon = next(
                (k for k, v in HORIZON_LABELS.items() if v == horizon_label),
                "current",
            )
        st.markdown("---")

        if view == "map":
            show_map(indicator_id, horizon)
        elif view == "ranking":
            show_ranking(horizon)
        elif view == "compare":
            show_comparison(horizon)
        elif view == "detail":
            pref_options = [f"{code} {name}" for code, name in PREFECTURE_NAMES.items()]
            chosen_pref = st.selectbox(
                "都道府県を選択",
                options=pref_options,
                index=12,  # 東京都
                key="selected_prefecture",
            )
            chosen_code = chosen_pref.split(" ", 1)[0]
            show_prefecture_detail(chosen_code)
        elif view == "model":
            show_model_detail(indicator_id)

    # 各セクション画面下にも免責 + ソース
    st.markdown("---")
    render_disclaimer()
    st.markdown("---")
    show_data_sources(None)


# 法務リンクフッター(INV-BIZ-008、DEC-016 派生)
render_footer()
