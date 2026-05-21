"""グローバル CSS / UI ヘルパー(50-60 代向けの可読性・アクセシビリティ強化).

主な配慮:
    - 基本フォントサイズを 17-18px に引き上げ
    - 行間を 1.6 に
    - 見出しに色とウェイト
    - ボタン/ラジオ/タブのタップ領域を 44px 以上
    - リンクのコントラスト確保(WCAG AA)
    - 印刷モード(@media print)でサイドバー/タブ非表示、フォント縮小
    - 印刷モード切替フラグ(セッション状態経由)で本文レイアウトも調整
"""

from __future__ import annotations

import streamlit as st

_GLOBAL_CSS = """
<style>
/* ---- Base typography (50-60 代向けに大きめ + 行間広め) ---- */
html, body, [class*="css"], [data-testid="stMarkdownContainer"] p {
    font-size: 17px !important;
    line-height: 1.65 !important;
}
/* 見出し */
h1, h1 span { font-size: 2.2rem !important; font-weight: 700 !important; color: #1f4068 !important; }
h2, h2 span { font-size: 1.7rem !important; font-weight: 700 !important; color: #1f4068 !important; margin-top: 0.8em !important; }
h3, h3 span { font-size: 1.35rem !important; font-weight: 700 !important; color: #1f4068 !important; }
h4, h4 span { font-size: 1.15rem !important; font-weight: 700 !important; }

/* ---- メトリック(大きな数字) ---- */
[data-testid="stMetricValue"] { font-size: 1.9rem !important; font-weight: 700 !important; }
[data-testid="stMetricLabel"] { font-size: 1rem !important; font-weight: 600 !important; }

/* ---- ラジオ・チェック・セレクト・スライダー ---- */
[data-testid="stRadio"] label,
[data-testid="stCheckbox"] label,
[data-testid="stSelectbox"] label,
[data-testid="stMultiSelect"] label,
[data-testid="stSlider"] label {
    font-size: 1.05rem !important;
    font-weight: 600 !important;
}
[data-testid="stRadio"] > div > label,
[data-testid="stCheckbox"] > label > div {
    padding: 0.35em 0 !important;
}

/* ---- ボタンを大きく(タップ領域 44px+) ---- */
.stButton button, .stDownloadButton button {
    font-size: 1.05rem !important;
    padding: 0.6em 1.4em !important;
    border-radius: 8px !important;
    font-weight: 600 !important;
    min-height: 44px !important;
}

/* ---- タブ ---- */
button[data-baseweb="tab"] {
    font-size: 1.1rem !important;
    padding: 0.9em 1.4em !important;
    font-weight: 600 !important;
}

/* ---- キャプション(補足) のコントラスト ---- */
[data-testid="stCaptionContainer"], .stCaption {
    color: #4a4a5e !important;
    font-size: 0.95rem !important;
}

/* ---- リンク ---- */
a, a:visited { color: #1f4068 !important; font-weight: 500 !important; text-decoration: underline !important; }
a:hover { color: #0d2547 !important; }

/* ---- info/warning/success のフォント ---- */
[data-testid="stAlert"] p { font-size: 1rem !important; line-height: 1.55 !important; }

/* ---- データフレームのフォント ---- */
[data-testid="stDataFrame"] div[role="cell"] { font-size: 0.95rem !important; }

/* ---- カードコンテナの余白(st.container(border=True)) ---- */
[data-testid="stHorizontalBlock"] > div { gap: 0.6rem !important; }

/* ---- ヒーローバナー(タイトル直下のキャッチコピー) ---- */
.movemap-hero {
    background: linear-gradient(135deg, #1f4068 0%, #3b6ea5 100%);
    color: white;
    padding: 1.4rem 1.8rem;
    border-radius: 12px;
    margin: 0.5rem 0 1.2rem 0;
    box-shadow: 0 4px 14px rgba(31, 64, 104, 0.18);
}
.movemap-hero h2 {
    color: white !important;
    margin-top: 0 !important;
    margin-bottom: 0.4rem !important;
    font-size: 1.6rem !important;
}
.movemap-hero p {
    color: rgba(255,255,255,0.95) !important;
    font-size: 1.05rem !important;
    margin: 0 !important;
    line-height: 1.55 !important;
}

/* ---- ステップガイド(タブ冒頭の案内カード) ---- */
.movemap-guide {
    background: #eef4fb;
    border-left: 4px solid #3b6ea5;
    padding: 0.9rem 1.1rem;
    border-radius: 6px;
    margin-bottom: 1rem;
    color: #1a1a2e;
    font-size: 1rem;
}
.movemap-guide strong { color: #1f4068; }

/* ---- 印刷モード ---- */
@media print {
    [data-testid="stSidebar"] { display: none !important; }
    [data-testid="stHeader"] { display: none !important; }
    button[data-baseweb="tab"] { display: none !important; }
    [data-testid="stTabs"] [data-baseweb="tab-list"] { display: none !important; }
    .movemap-hero { background: white !important; color: black !important; box-shadow: none !important; border: 1px solid #999; }
    .movemap-hero h2, .movemap-hero p { color: black !important; }
    html, body { font-size: 12pt !important; }
}

/* ---- モバイル対応(画面幅 768px 以下) ---- */
@media (max-width: 768px) {
    /* ヒーローバナーを縦コンパクトに */
    .movemap-hero { padding: 0.85rem 1rem !important; margin: 0.3rem 0 0.7rem 0 !important; border-radius: 8px !important; }
    .movemap-hero h2 { font-size: 1.18rem !important; margin-bottom: 0.3rem !important; }
    .movemap-hero p { font-size: 0.92rem !important; line-height: 1.45 !important; }
    /* 見出しサイズダウン(縦が貴重なので) */
    h1, h1 span { font-size: 1.55rem !important; }
    h2, h2 span { font-size: 1.3rem !important; }
    h3, h3 span { font-size: 1.12rem !important; }
    h4, h4 span { font-size: 1.02rem !important; }
    /* ガイドカード縮小 */
    .movemap-guide { padding: 0.6rem 0.85rem !important; font-size: 0.92rem !important; line-height: 1.5 !important; }
    /* タブを少し詰めて全タブが見えるように */
    button[data-baseweb="tab"] { padding: 0.6em 0.5em !important; font-size: 0.95rem !important; font-weight: 700 !important; }
    [data-testid="stTabs"] [data-baseweb="tab-list"] { gap: 0 !important; }
    /* ボタンも少しコンパクト(ただしタップ領域 44px 維持) */
    .stButton button, .stDownloadButton button {
        padding: 0.55em 1em !important;
        font-size: 1rem !important;
        min-height: 44px !important;
    }
    /* 本文フォントを少しだけ小さく(画面幅優先) */
    html, body, [class*="css"], [data-testid="stMarkdownContainer"] p {
        font-size: 16px !important;
        line-height: 1.55 !important;
    }
    /* メトリック数字も縮小 */
    [data-testid="stMetricValue"] { font-size: 1.5rem !important; }
    [data-testid="stMetricLabel"] { font-size: 0.9rem !important; }
    /* 「現在の選択」サマリバンドのスマホ調整 */
    .movemap-current-band {
        font-size: 1rem !important;
        padding: 0.6rem 0.8rem !important;
    }
    .movemap-current-band strong { font-size: 1.05rem !important; }
    /* スマホ案内バナー(モバイルでだけ表示) */
    .movemap-mobile-hint { display: block !important; }
}

/* デスクトップでは非表示(スマホ案内バナー) */
.movemap-mobile-hint { display: none; }

/* ---- 「現在の選択」サマリバンド(画面上部) ---- */
.movemap-current-band {
    background: #f5f7fa;
    border: 1px solid #d8e0ea;
    border-left: 5px solid #1f4068;
    padding: 0.7rem 1.1rem;
    border-radius: 6px;
    margin: 0.4rem 0 1rem 0;
    font-size: 1.05rem;
    color: #1a1a2e;
}
.movemap-current-band strong { color: #1f4068; font-size: 1.1rem; }
.movemap-current-band .sep { color: #999; margin: 0 0.5rem; }

/* ---- スマホ案内バナー ---- */
.movemap-mobile-hint {
    background: #fff8e1;
    border: 1px solid #ffd54f;
    border-radius: 6px;
    padding: 0.55rem 0.9rem;
    margin: 0.3rem 0 0.8rem 0;
    font-size: 0.95rem;
    color: #6d4c00;
}
</style>
"""


_HERO_HTML = """
<div class="movemap-hero">
  <h2>🗾 あなたに合う地方移住先を、データで見つける</h2>
  <p>全国 47 都道府県を 7 つの観点(物価・地価・賃料・出生数・空気質・災害リスク・交通アクセス)で比較。<br>
  AI 予測で 3 / 5 / 10 年先の変化も先取りできます。</p>
</div>
"""


def inject_global_css() -> None:
    """ページ冒頭で 1 回呼び出す. グローバル CSS を <style> として挿入."""
    st.markdown(_GLOBAL_CSS, unsafe_allow_html=True)


def render_hero() -> None:
    """タイトル下のヒーローバナー(キャッチコピー)."""
    st.markdown(_HERO_HTML, unsafe_allow_html=True)


def render_tab_guide(text: str) -> None:
    """各タブ冒頭の薄青ガイドカード.

    Args:
        text: HTML 可。<strong> や <br> 利用可.
    """
    st.markdown(f'<div class="movemap-guide">{text}</div>', unsafe_allow_html=True)


def render_current_band(indicator_html: str, horizon_label: str) -> None:
    """画面上部に「現在の選択」を大きく表示するサマリバンド.

    スマホでサイドバーが隠れている時も、何を見ているかが一目で分かる.
    """
    st.markdown(
        f'<div class="movemap-current-band">'
        f"📊 観点: <strong>{indicator_html}</strong>"
        f'<span class="sep">｜</span>'
        f"📅 時点: <strong>{horizon_label}</strong>"
        f"</div>",
        unsafe_allow_html=True,
    )


def render_mobile_hint() -> None:
    """スマホで開いた時だけ表示される操作案内バナー(CSS で表示制御)."""
    st.markdown(
        '<div class="movemap-mobile-hint">'
        "📱 スマホからご利用の場合、観点・時点の変更は左上の "
        "<strong>☰ メニュー</strong> から行えます。"
        "</div>",
        unsafe_allow_html=True,
    )


__all__ = [
    "inject_global_css",
    "render_current_band",
    "render_hero",
    "render_mobile_hint",
    "render_tab_guide",
]
