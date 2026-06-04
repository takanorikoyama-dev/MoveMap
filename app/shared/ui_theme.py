"""グローバル CSS / UI ヘルパー(50-60 代向けの可読性・アクセシビリティ強化).

主な配慮:
    - 基本フォントサイズを 17-18px に引き上げ
    - 行間を 1.6 に
    - 見出しに色とウェイト
    - ボタン/ラジオ/タブのタップ領域を 44px 以上
    - リンクのコントラスト確保(WCAG AA)
    - 印刷モード(@media print)でサイドバー/タブ非表示、フォント縮小
    - 印刷モード切替フラグ(セッション状態経由)で本文レイアウトも調整

UI 刷新(2026-06-02):
    - 診断ページのファストビュー(render_hero)を Aman / 星のや 風に刷新
    - 全画面ヒーロー画像 + minimal overlay + 朱の CTA
    - 採用画像は Unsplash 由来、Phase 1 では岡山県(路地の自転車)を採用
    - Phase 2 で 47 県スライドショー化予定
"""

from __future__ import annotations

import streamlit as st
import streamlit.components.v1 as components

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

/* ====================================================
   ヒーロー(Aman 風 + 4 枚横スライド、海と自然テーマ)
   ==================================================== */
.movemap-hero {
    position: relative;
    width: 100%;
    height: 60vh;
    min-height: 460px;
    max-height: 680px;
    margin: -2rem -3rem 1.5rem -3rem;
    overflow: hidden;
    font-family: -apple-system, BlinkMacSystemFont, "Hiragino Sans",
                 "Yu Gothic UI", "Helvetica Neue", sans-serif;
    background: #1a1a1a;
}
.movemap-hero-track {
    position: absolute;
    inset: 0;
    display: flex;
    /* 5 スライド分(4 枚 + 1 枚目の複製でシームレスループ) */
    width: 500%;
    transform: translateX(0%);
    /* 切替アニメは JS が動的に付与 */
    will-change: transform;
}
.movemap-hero-slide {
    flex: 0 0 20%;       /* 5 枚なので 20% ずつ */
    height: 100%;
    background-size: cover;
    background-position: center 55%;
    background-repeat: no-repeat;
}

/* 左右の手動切替矢印(ホバー時のみ濃く) */
.movemap-hero-arrow {
    position: absolute;
    top: 50%;
    transform: translateY(-50%);
    width: 52px;
    height: 52px;
    background: rgba(0, 0, 0, 0.28);
    color: #ffffff;
    border: 1px solid rgba(255, 255, 255, 0.4);
    cursor: pointer;
    font-size: 1.6rem;
    line-height: 1;
    font-weight: 300;
    z-index: 3;
    transition: background 0.2s, transform 0.2s, opacity 0.2s;
    opacity: 0.65;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 0;
}
.movemap-hero:hover .movemap-hero-arrow { opacity: 1; }
.movemap-hero-arrow:hover { background: rgba(0, 0, 0, 0.6); }
.movemap-hero-arrow:active { transform: translateY(-50%) scale(0.94); }
.movemap-hero-arrow-prev { left: 1.2rem; }
.movemap-hero-arrow-next { right: 1.2rem; }

/* ドットインジケータ(現在表示中スライドを示す) */
.movemap-hero-dots {
    position: absolute;
    bottom: 4.2rem;
    left: 50%;
    transform: translateX(-50%);
    z-index: 3;
    display: flex;
    gap: 0.6rem;
}
.movemap-hero-dot {
    width: 10px;
    height: 10px;
    border-radius: 50%;
    background: rgba(255, 255, 255, 0.45);
    cursor: pointer;
    border: 1px solid rgba(255, 255, 255, 0.85);
    transition: background 0.25s, transform 0.2s;
    padding: 0;
}
.movemap-hero-dot:hover { background: rgba(255, 255, 255, 0.85); }
.movemap-hero-dot.active {
    background: #ffffff;
    transform: scale(1.25);
}
@media (max-width: 768px) {
    .movemap-hero-arrow { width: 42px; height: 42px; font-size: 1.3rem; }
    .movemap-hero-arrow-prev { left: 0.7rem; }
    .movemap-hero-arrow-next { right: 0.7rem; }
    .movemap-hero-dots { bottom: 3.4rem; }
}
.movemap-hero-overlay {
    position: absolute;
    inset: 0;
    /* 画像を主役にするため、暗さを大幅軽減(明るく) */
    background:
        linear-gradient(180deg,
            rgba(10, 10, 14, 0.16) 0%,
            rgba(10, 10, 14, 0.05) 40%,
            rgba(10, 10, 14, 0.35) 100%);
    z-index: 1;
}
.movemap-hero-content {
    position: relative;
    height: 100%;
    z-index: 2;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    text-align: center;
    color: #ffffff;
    padding: 0 1.5rem;
}
.movemap-hero-brand {
    position: absolute;
    top: 1.6rem;
    left: 2.2rem;
    font-size: 1.05rem;
    font-weight: 700;
    letter-spacing: 0.3em;
    color: #ffffff;
    text-shadow: 0 2px 10px rgba(0, 0, 0, 0.6);
    z-index: 2;
}
.movemap-hero-brand::before {
    content: "M";
    display: inline-block;
    margin-right: 0.55rem;
    color: #ff6b5e;
    font-weight: 800;
}
.movemap-hero-title,
.movemap-hero-title *,
.movemap-hero-title strong,
.movemap-hero-title span {
    /* どんな子要素にも純白を強制(global CSS の h1 色を上書き) */
    color: #ffffff !important;
}
.movemap-hero-title {
    /* 横 1 行 × 大幅拡大(2 倍弱) */
    font-size: clamp(3.6rem, 9vw, 8.5rem) !important;
    font-weight: 700 !important;
    line-height: 1.15 !important;
    letter-spacing: 0.04em !important;
    margin: 0 0 1.8rem 0 !important;
    white-space: nowrap;                  /* 横 1 行を強制 */
    text-shadow:
        0 2px 10px rgba(0, 0, 0, 0.6),
        0 4px 28px rgba(0, 0, 0, 0.5);
}
.movemap-hero-title strong {
    font-weight: 800 !important;
}
.movemap-hero-sub {
    /* 3 倍弱 */
    font-size: clamp(3.0rem, 6vw, 5.4rem) !important;
    font-weight: 600 !important;
    letter-spacing: 0.26em !important;
    color: #ffffff !important;
    margin: 0 0 2.8rem 0 !important;
    text-shadow:
        0 2px 10px rgba(0, 0, 0, 0.65),
        0 4px 22px rgba(0, 0, 0, 0.55);
    padding-left: 0.26em;
}
.movemap-hero-cta {
    display: inline-block;
    padding: 1.3rem 3.8rem !important;
    font-size: 1.25rem !important;
    font-weight: 700 !important;
    letter-spacing: 0.18em;
    color: #1a1a1a !important;
    background: #ffffff !important;
    border: 2px solid #ffffff !important;
    border-radius: 2px !important;
    cursor: pointer;
    transition: background 0.3s, color 0.3s, transform 0.2s, box-shadow 0.3s;
    text-decoration: none !important;
    box-shadow: 0 4px 22px rgba(0, 0, 0, 0.3);
}
.movemap-hero-cta:hover {
    background: #ff6b5e !important;
    color: #ffffff !important;
    border-color: #ff6b5e !important;
    text-decoration: none !important;
    box-shadow: 0 6px 28px rgba(255, 107, 94, 0.5);
    transform: translateY(-1px);
}
.movemap-hero-cta:active { transform: translateY(1px); }
.movemap-hero-scroll {
    position: absolute;
    bottom: 1.2rem;
    left: 50%;
    transform: translateX(-50%);
    color: #ffffff;
    font-size: 0.95rem;
    font-weight: 500;
    letter-spacing: 0.24em;
    text-shadow: 0 2px 8px rgba(0, 0, 0, 0.6);
    animation: heroScrollHint 2.4s ease-in-out infinite;
    z-index: 2;
}
@keyframes heroScrollHint {
    0%, 100% { opacity: 0.65; transform: translate(-50%, 0); }
    50%      { opacity: 1.0;  transform: translate(-50%, 7px); }
}
.movemap-hero-credit {
    position: absolute;
    bottom: 1.1rem;
    right: 1.6rem;
    font-size: 0.7rem;
    letter-spacing: 0.06em;
    color: rgba(255, 255, 255, 0.72);
    text-shadow: 0 1px 4px rgba(0, 0, 0, 0.6);
    z-index: 2;
}
.movemap-hero-credit a {
    color: rgba(255, 255, 255, 0.85) !important;
    text-decoration: none !important;
    font-weight: 400 !important;
}
.movemap-hero-credit a:hover {
    color: #ffffff !important;
    text-decoration: underline !important;
}

/* ====================================================
   セクションバナー(ホームのコンテンツ入口)
   ==================================================== */
.movemap-section-grid {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 1.4rem;
    margin: 2.5rem 0 1.5rem;
}
.movemap-section-banner,
.movemap-section-banner-visual {
    position: relative;
    display: block;
    width: 100%;
    aspect-ratio: 16 / 7;
    overflow: hidden;
    background: #1a1a1a;
    transition: transform 0.3s, box-shadow 0.3s;
    text-decoration: none !important;
    color: inherit;
}
.movemap-section-banner:hover,
.movemap-section-banner-visual:hover {
    transform: scale(1.01);
    box-shadow: 0 12px 36px rgba(0,0,0,0.3);
    text-decoration: none !important;
}
.movemap-section-banner-bg {
    position: absolute;
    inset: 0;
    background-size: cover;
    background-position: center 50%;
    transition: transform 0.6s, filter 0.4s;
}
.movemap-section-banner:hover .movemap-section-banner-bg {
    transform: scale(1.05);
    filter: brightness(1.08);
}
.movemap-section-banner-overlay {
    position: absolute;
    inset: 0;
    background: linear-gradient(135deg,
        rgba(10,10,14,0.55) 0%,
        rgba(10,10,14,0.18) 50%,
        rgba(10,10,14,0.55) 100%);
}
.movemap-section-banner-text {
    position: absolute;
    inset: 0;
    z-index: 2;
    display: flex;
    flex-direction: column;
    justify-content: center;
    align-items: flex-start;
    padding: 1.6rem 2.2rem;
    color: #ffffff;
    text-shadow: 0 2px 10px rgba(0,0,0,0.5);
}
.movemap-section-banner-title {
    /* 2 倍 */
    font-size: 3.2rem;
    font-weight: 700;
    letter-spacing: 0.1em;
    margin-bottom: 0.6rem;
    color: #ffffff;
    text-shadow: 0 2px 12px rgba(0,0,0,0.65);
}
.movemap-section-banner-desc {
    /* 2 倍 → さらに 2/3 に縮小 */
    font-size: 1.27rem;
    font-weight: 500;
    letter-spacing: 0.04em;
    color: #ffffff;
    line-height: 1.45;
    text-shadow: 0 2px 10px rgba(0,0,0,0.6);
}
.movemap-section-banner-cta {
    margin-top: 1.2rem;
    font-size: 1.5rem;
    font-weight: 700;
    letter-spacing: 0.18em;
    color: #ffffff;
    border-bottom: 3px solid #ff6b5e;
    padding-bottom: 0.3rem;
    text-shadow: 0 2px 8px rgba(0,0,0,0.55);
}
@media (max-width: 768px) {
    .movemap-section-grid { grid-template-columns: 1fr; gap: 1rem; }
    .movemap-section-banner { aspect-ratio: 16 / 9; }
    .movemap-section-banner-title { font-size: 2.0rem; letter-spacing: 0.06em; }
    .movemap-section-banner-desc { font-size: 0.73rem; }
    .movemap-section-banner-cta { font-size: 1.05rem; }
    /* モバイルではメインコピーは折り返し可(画面幅優先) */
    .movemap-hero-title { white-space: normal !important; }
}

/* ====================================================
   ヒーロー外 CTA(iframe の sandbox 制約で内部 CTA から
   親窓 navigate ができないため、メインページ側に CTA を出して
   負マージンでヒーロー上にオーバーレイ配置)
   ==================================================== */
.movemap-hero-cta-row {
    margin: -130px 0 1.4rem 0;       /* ヒーロー下端あたりに重ねる */
    text-align: center;
    position: relative;
    z-index: 50;
    pointer-events: none;             /* バナー外側はクリック透過、リンク自身のみ受け取る */
}
.movemap-hero-cta-link {
    display: inline-block;
    pointer-events: auto;
    padding: 1.3rem 3.8rem;
    font-size: 1.25rem;
    font-weight: 700;
    letter-spacing: 0.18em;
    color: #1a1a1a !important;
    background: #ffffff !important;
    border: 2px solid #ffffff !important;
    border-radius: 2px;
    text-decoration: none !important;
    box-shadow: 0 4px 22px rgba(0,0,0,0.32);
    transition: background 0.25s, color 0.25s, border-color 0.25s, box-shadow 0.25s, transform 0.2s;
}
.movemap-hero-cta-link:hover {
    background: #ff6b5e !important;
    color: #ffffff !important;
    border-color: #ff6b5e !important;
    box-shadow: 0 6px 28px rgba(255,107,94,0.5);
    transform: translateY(-1px);
    text-decoration: none !important;
}
.movemap-hero-cta-link:active { transform: translateY(1px); }
@media (max-width: 768px) {
    .movemap-hero-cta-row { margin-top: -110px; }
    .movemap-hero-cta-link { padding: 1rem 2.6rem !important; font-size: 1.05rem !important; }
}

/* ====================================================
   「← ホームに戻る」リンク(各セクション画面上部)
   ==================================================== */
.movemap-back-link {
    display: inline-block;
    padding: 0.6rem 1.2rem;
    font-size: 1.0rem;
    font-weight: 500;
    letter-spacing: 0.06em;
    color: #1f4068 !important;
    background: transparent;
    border: 1px solid #1f4068;
    border-radius: 4px;
    text-decoration: none !important;
    transition: background 0.2s, color 0.2s;
    margin-bottom: 0.8rem;
}
.movemap-back-link:hover {
    background: #1f4068;
    color: #ffffff !important;
    text-decoration: none !important;
}

/* ====================================================
   サイドバー非表示(2026-06-02 デザイン刷新)
   ==================================================== */
[data-testid="stSidebar"] { display: none !important; }
[data-testid="collapsedControl"] { display: none !important; }
/* ヘッダ余白も詰める(ヒーローを画面いっぱいに) */
[data-testid="stHeader"] { background: transparent !important; }
[data-testid="stMainBlockContainer"],
[data-testid="stMain"] > div:first-child {
    padding-top: 0 !important;
}
.block-container {
    padding-top: 0 !important;
    padding-left: 3rem !important;
    padding-right: 3rem !important;
    max-width: none !important;
}
@media (max-width: 768px) {
    .block-container { padding-left: 1rem !important; padding-right: 1rem !important; }
    .movemap-hero { margin-left: -1rem !important; margin-right: -1rem !important; }
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
    /* ヒーローはモバイルでも 60vh、ボタンも見やすく */
    .movemap-hero { height: 60vh; min-height: 420px; margin-top: -1.2rem !important; }
    .movemap-hero-brand { top: 1.0rem; left: 1.1rem; font-size: 0.9rem; letter-spacing: 0.22em; }
    .movemap-hero-title { letter-spacing: 0.03em !important; margin-bottom: 1.0rem !important; }
    .movemap-hero-sub { letter-spacing: 0.22em !important; margin-bottom: 1.6rem !important; }
    .movemap-hero-cta { padding: 1.0rem 2.4rem !important; font-size: 1.05rem !important; }
    .movemap-hero-credit { font-size: 0.64rem; right: 0.9rem; bottom: 0.8rem; }
    .movemap-hero-scroll { font-size: 0.82rem; }
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


# ヒーロー: 海と自然テーマの 4 枚自動横スライド(3 秒ごと)
# 1: 千葉 灯台+海 / 2: 鳥取 砂浜+波 / 3: 静岡 富士山 / 4: 福井 池+森
_HERO_SLIDES = [
    "https://images.unsplash.com/photo-1652963212851-bfc736ce2ff3?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&q=85&w=2400",
    "https://images.unsplash.com/photo-1635902918331-10e4952b3920?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&q=85&w=2400",
    "https://images.unsplash.com/photo-1708446637293-13b8dddbc97b?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&q=85&w=2400",
    "https://images.unsplash.com/photo-1722035193444-54e198dcd2fc?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&q=85&w=2400",
]
# 4 枚目の後に 1 枚目を足してループ時のシーム消し(translate -100% で 1 枚目に戻る)
_HERO_SLIDES_LOOP = _HERO_SLIDES + [_HERO_SLIDES[0]]
_HERO_CREDIT_HTML = 'Photos: <a href="https://unsplash.com" target="_blank" rel="noopener">Unsplash</a>'


_HERO_SLIDE_LABELS = [
    "千葉県の海岸と灯台 — 海と自然のある暮らし",
    "鳥取砂丘 — 雄大な日本の海景",
    "静岡県の富士山 — 日本の象徴的な山",
    "福井県の池と森 — 静かな自然と暮らし",
]


def _build_hero_iframe_html() -> str:
    """`components.html` で描画する完結ヒーロー(iframe 内で JS 実行).

    Streamlit の st.markdown 内では <script> が実行されないため、
    iframe 描画が必須. 内部に独立 CSS + JS を持ち、本ファイル外の
    グローバル CSS には依存しない. SEO/アクセシビリティ:各スライドに
    role="img" + aria-label を付与.
    """
    slides_html = "".join(
        f'<div class="slide" role="img" aria-label="{_HERO_SLIDE_LABELS[i % len(_HERO_SLIDE_LABELS)]}" '
        f'style="background-image: url(\'{url}\');"></div>'
        for i, url in enumerate(_HERO_SLIDES_LOOP)
    )
    n_unique = len(_HERO_SLIDES)
    dots_html = "".join(
        f'<button class="dot{" active" if i == 0 else ""}" '
        f'data-idx="{i}" aria-label="スライド {i+1}"></button>'
        for i in range(n_unique)
    )
    return f"""<!DOCTYPE html>
<html lang="ja"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<style>
  html, body {{ margin: 0; padding: 0; height: 100%; overflow: hidden;
                font-family: -apple-system, BlinkMacSystemFont, "Hiragino Sans",
                             "Yu Gothic UI", sans-serif; background: #1a1a1a; }}
  .hero {{ position: relative; width: 100%; height: 100vh; overflow: hidden; }}
  .track {{ position: absolute; inset: 0; display: flex;
            width: {(n_unique + 1) * 100}%; transform: translateX(0%); will-change: transform; }}
  .slide {{ flex: 0 0 {100 / (n_unique + 1)}%; height: 100%;
            background-size: cover; background-position: center 55%; background-repeat: no-repeat; }}
  .overlay {{ position: absolute; inset: 0;
              background: linear-gradient(180deg,
                rgba(10,10,14,0.16) 0%, rgba(10,10,14,0.05) 40%, rgba(10,10,14,0.4) 100%);
              z-index: 1; pointer-events: none; }}
  .content {{ position: relative; height: 100%; z-index: 2;
              display: flex; flex-direction: column; align-items: center; justify-content: center;
              text-align: center; color: #fff; padding: 0 1.5rem; pointer-events: none; }}
  .content > * {{ pointer-events: auto; }}
  .brand {{ position: absolute; top: 1.6rem; left: 2.2rem; z-index: 2;
            font-size: 1.05rem; font-weight: 700; letter-spacing: 0.3em; color: #fff;
            text-shadow: 0 2px 10px rgba(0,0,0,0.6); }}
  .brand::before {{ content: "M"; margin-right: 0.55rem; color: #ff6b5e; font-weight: 800; }}
  h1 {{ font-size: clamp(1.8rem, 4.5vw, 4.25rem); font-weight: 700; line-height: 1.15;
        letter-spacing: 0.04em; margin: 0 0 1.2rem 0; color: #fff !important; white-space: nowrap;
        text-shadow: 0 2px 10px rgba(0,0,0,0.6), 0 4px 28px rgba(0,0,0,0.5); }}
  h1 strong {{ font-weight: 800; color: #fff !important; }}
  .sub {{ font-size: clamp(1.5rem, 3vw, 2.7rem); font-weight: 600; letter-spacing: 0.26em;
          color: #fff; margin: 0 0 2.0rem 0;
          text-shadow: 0 2px 10px rgba(0,0,0,0.65), 0 4px 22px rgba(0,0,0,0.55);
          padding-left: 0.26em; }}
  .cta {{ display: inline-block; padding: 1.3rem 3.8rem; font-size: 1.25rem; font-weight: 700;
          letter-spacing: 0.18em; color: #1a1a1a !important; background: #fff;
          border: 2px solid #fff; border-radius: 2px; cursor: pointer; text-decoration: none !important;
          box-shadow: 0 4px 22px rgba(0,0,0,0.3); transition: all 0.25s; }}
  .cta:hover {{ background: #ff6b5e; color: #fff !important; border-color: #ff6b5e;
                box-shadow: 0 6px 28px rgba(255,107,94,0.5); transform: translateY(-1px); }}
  .arrow {{ position: absolute; top: 50%; transform: translateY(-50%); width: 52px; height: 52px;
            background: rgba(0,0,0,0.32); color: #fff; border: 1px solid rgba(255,255,255,0.45);
            font-size: 1.7rem; font-weight: 300; cursor: pointer; z-index: 3;
            display: flex; align-items: center; justify-content: center; padding: 0;
            opacity: 0.7; transition: all 0.2s; }}
  .hero:hover .arrow {{ opacity: 1; }}
  .arrow:hover {{ background: rgba(0,0,0,0.7); }}
  .arrow:active {{ transform: translateY(-50%) scale(0.94); }}
  .arrow.prev {{ left: 1.2rem; }}
  .arrow.next {{ right: 1.2rem; }}
  .dots {{ position: absolute; bottom: 4rem; left: 50%; transform: translateX(-50%);
           display: flex; gap: 0.6rem; z-index: 3; }}
  .dot {{ width: 11px; height: 11px; border-radius: 50%;
          background: rgba(255,255,255,0.45); border: 1px solid rgba(255,255,255,0.85);
          cursor: pointer; padding: 0; transition: all 0.25s; }}
  .dot:hover {{ background: rgba(255,255,255,0.85); }}
  .dot.active {{ background: #fff; transform: scale(1.3); }}
  .scroll {{ position: absolute; bottom: 1.2rem; left: 50%; transform: translateX(-50%);
             color: #fff; font-size: 0.95rem; font-weight: 500; letter-spacing: 0.24em;
             text-shadow: 0 2px 8px rgba(0,0,0,0.6); z-index: 2;
             animation: scrollHint 2.4s ease-in-out infinite; }}
  @keyframes scrollHint {{
    0%, 100% {{ opacity: 0.65; transform: translate(-50%, 0); }}
    50%      {{ opacity: 1.0;  transform: translate(-50%, 7px); }}
  }}
  .credit {{ position: absolute; bottom: 1.1rem; right: 1.6rem;
             font-size: 0.7rem; letter-spacing: 0.06em;
             color: rgba(255,255,255,0.72); text-shadow: 0 1px 4px rgba(0,0,0,0.6); z-index: 2; }}
  .credit a {{ color: rgba(255,255,255,0.85); text-decoration: none; }}
  .credit a:hover {{ color: #fff; text-decoration: underline; }}
  @media (max-width: 768px) {{
    .brand {{ top: 1rem; left: 1.1rem; font-size: 0.9rem; letter-spacing: 0.22em; }}
    h1 {{ white-space: normal; letter-spacing: 0.03em; margin-bottom: 1rem; }}
    .sub {{ letter-spacing: 0.22em; margin-bottom: 1.6rem; }}
    .cta {{ padding: 1rem 2.4rem; font-size: 1.05rem; }}
    .arrow {{ width: 42px; height: 42px; font-size: 1.3rem; }}
    .arrow.prev {{ left: 0.7rem; }}
    .arrow.next {{ right: 0.7rem; }}
    .dots {{ bottom: 3.3rem; }}
    .credit {{ font-size: 0.64rem; right: 0.9rem; bottom: 0.8rem; }}
    .scroll {{ font-size: 0.82rem; }}
  }}
</style></head>
<body>
  <div class="hero" id="hero">
    <div class="track" id="track">{slides_html}</div>
    <div class="overlay"></div>
    <div class="brand">MoveMap</div>
    <button class="arrow prev" id="prev" aria-label="前のスライド">‹</button>
    <button class="arrow next" id="next" aria-label="次のスライド">›</button>
    <div class="content">
      <h1>まだ知らない、<strong>わたしのまち。</strong></h1>
      <p class="sub">移住を、データで。</p>
    </div>
    <div class="dots" id="dots">{dots_html}</div>
    <div class="scroll">SCROLL ⌄</div>
    <div class="credit">{_HERO_CREDIT_HTML}</div>
  </div>
  <script>
    (function() {{
      const TOTAL = {n_unique};
      const STEP = 100 / (TOTAL + 1);    // 5 スライドなので 20%
      const AUTO_MS = 3000;
      const ANIM_MS = 700;
      let idx = 0;
      let autoTimer = null;
      const track = document.getElementById('track');

      function setPos(targetIdx, withAnim) {{
        track.style.transition = withAnim ? `transform ${{ANIM_MS}}ms ease-in-out` : 'none';
        track.style.transform = `translateX(-${{targetIdx * STEP}}%)`;
      }}
      function updateDots() {{
        const realIdx = idx % TOTAL;
        document.querySelectorAll('.dot').forEach((d, i) => {{
          d.classList.toggle('active', i === realIdx);
        }});
      }}
      function next() {{
        idx++;
        setPos(idx, true);
        updateDots();
        if (idx === TOTAL) {{
          setTimeout(() => {{ idx = 0; setPos(0, false); }}, ANIM_MS + 20);
        }}
      }}
      function prev() {{
        if (idx === 0) {{
          idx = TOTAL;
          setPos(idx, false);
          setTimeout(() => {{ idx = TOTAL - 1; setPos(idx, true); updateDots(); }}, 30);
        }} else {{
          idx--;
          setPos(idx, true);
          updateDots();
        }}
      }}
      function goTo(targetIdx) {{
        idx = Math.max(0, Math.min(TOTAL - 1, targetIdx));
        setPos(idx, true);
        updateDots();
      }}
      function resetAuto() {{
        if (autoTimer) clearInterval(autoTimer);
        autoTimer = setInterval(next, AUTO_MS);
      }}

      setPos(0, false);
      resetAuto();

      document.getElementById('prev').addEventListener('click', () => {{ prev(); resetAuto(); }});
      document.getElementById('next').addEventListener('click', () => {{ next(); resetAuto(); }});
      document.querySelectorAll('.dot').forEach((d) => {{
        d.addEventListener('click', () => {{
          const i = parseInt(d.getAttribute('data-idx') || '0', 10);
          goTo(i); resetAuto();
        }});
      }});

      // タッチ・スワイプ
      const hero = document.getElementById('hero');
      let touchStartX = 0;
      hero.addEventListener('touchstart', (e) => {{ touchStartX = e.touches[0].clientX; }}, {{ passive: true }});
      hero.addEventListener('touchend', (e) => {{
        const diff = e.changedTouches[0].clientX - touchStartX;
        if (Math.abs(diff) > 50) {{
          if (diff < 0) next(); else prev();
          resetAuto();
        }}
      }});
      hero.addEventListener('mouseenter', () => {{ if (autoTimer) clearInterval(autoTimer); }});
      hero.addEventListener('mouseleave', () => {{ resetAuto(); }});
    }})();
  </script>
</body></html>"""


def _build_hero_html() -> str:
    slides_html = "".join(
        f'<div class="movemap-hero-slide" style="background-image: url(\'{url}\');"></div>'
        for url in _HERO_SLIDES_LOOP
    )
    n_unique = len(_HERO_SLIDES)
    dots_html = "".join(
        f'<button class="movemap-hero-dot{" active" if i == 0 else ""}" '
        f'data-idx="{i}" aria-label="スライド {i+1}"></button>'
        for i in range(n_unique)
    )
    return f"""
<div class="movemap-hero" id="movemap-hero" aria-label="MoveMap ヒーロー">
  <div class="movemap-hero-track" id="movemap-hero-track">{slides_html}</div>
  <div class="movemap-hero-overlay"></div>
  <div class="movemap-hero-brand">MoveMap</div>
  <button class="movemap-hero-arrow movemap-hero-arrow-prev"
          id="movemap-hero-prev" aria-label="前のスライド">‹</button>
  <button class="movemap-hero-arrow movemap-hero-arrow-next"
          id="movemap-hero-next" aria-label="次のスライド">›</button>
  <div class="movemap-hero-content">
    <h1 class="movemap-hero-title">まだ知らない、<strong>わたしのまち。</strong></h1>
    <p class="movemap-hero-sub">移住を、データで。</p>
    <a class="movemap-hero-cta"
       href="javascript:window.scrollTo({{top: window.innerHeight * 0.62, left: 0, behavior: 'smooth'}});">
       診断を始める
    </a>
  </div>
  <div class="movemap-hero-dots" id="movemap-hero-dots">{dots_html}</div>
  <div class="movemap-hero-scroll">SCROLL ⌄</div>
  <div class="movemap-hero-credit">{_HERO_CREDIT_HTML}</div>
</div>
<script>
(function() {{
  // 既に初期化されている(rerun 等)なら最新の初期化フラグでスキップ
  const FLAG = "_movemapHeroInited_v2";
  if (window[FLAG]) return;
  window[FLAG] = true;

  const TOTAL = {n_unique};                // 4 枚(本物)
  const STEP = 100 / (TOTAL + 1);          // 5 スライドなので 20% 刻み
  const AUTO_MS = 3000;                    // 自動切替 3 秒
  const ANIM_MS = 700;                     // スライドのアニメ時間

  let idx = 0;          // 0 .. TOTAL(末尾は 1 枚目の複製)
  let autoTimer = null;

  const track = document.getElementById('movemap-hero-track');
  if (!track) return;

  function setPos(targetIdx, withAnim) {{
    track.style.transition = withAnim
      ? `transform ${{ANIM_MS}}ms ease-in-out`
      : 'none';
    track.style.transform = `translateX(-${{targetIdx * STEP}}%)`;
  }}

  function updateDots() {{
    const realIdx = idx % TOTAL;
    document.querySelectorAll('.movemap-hero-dot').forEach((d, i) => {{
      d.classList.toggle('active', i === realIdx);
    }});
  }}

  function next() {{
    idx++;
    setPos(idx, true);
    updateDots();
    if (idx === TOTAL) {{
      // 末尾=1枚目の複製. アニメ後に即座に先頭(0)へリセット(無アニメ)
      setTimeout(() => {{
        idx = 0;
        setPos(0, false);
      }}, ANIM_MS + 20);
    }}
  }}

  function prev() {{
    if (idx === 0) {{
      // 先頭から戻る: 一旦末尾(複製スライド=見た目同じ)へ無アニメで飛んでから本物の末尾へアニメ
      idx = TOTAL;
      setPos(idx, false);
      setTimeout(() => {{
        idx = TOTAL - 1;
        setPos(idx, true);
        updateDots();
      }}, 30);
    }} else {{
      idx--;
      setPos(idx, true);
      updateDots();
    }}
  }}

  function goTo(targetIdx) {{
    idx = Math.max(0, Math.min(TOTAL - 1, targetIdx));
    setPos(idx, true);
    updateDots();
  }}

  function resetAuto() {{
    if (autoTimer) clearInterval(autoTimer);
    autoTimer = setInterval(next, AUTO_MS);
  }}

  // 初期表示
  setPos(0, false);
  resetAuto();

  // 矢印
  const prevBtn = document.getElementById('movemap-hero-prev');
  const nextBtn = document.getElementById('movemap-hero-next');
  if (prevBtn) prevBtn.addEventListener('click', () => {{ prev(); resetAuto(); }});
  if (nextBtn) nextBtn.addEventListener('click', () => {{ next(); resetAuto(); }});

  // ドット
  document.querySelectorAll('.movemap-hero-dot').forEach((d) => {{
    d.addEventListener('click', () => {{
      const i = parseInt(d.getAttribute('data-idx') || '0', 10);
      goTo(i);
      resetAuto();
    }});
  }});

  // タッチ・スワイプ
  const hero = document.getElementById('movemap-hero');
  if (hero) {{
    let touchStartX = 0;
    let touchEndX = 0;
    hero.addEventListener('touchstart', (e) => {{
      touchStartX = e.touches[0].clientX;
    }}, {{ passive: true }});
    hero.addEventListener('touchend', (e) => {{
      touchEndX = e.changedTouches[0].clientX;
      const diff = touchEndX - touchStartX;
      if (Math.abs(diff) > 50) {{
        if (diff < 0) next(); else prev();
        resetAuto();
      }}
    }});
    // ホバー中は自動切替を一時停止
    hero.addEventListener('mouseenter', () => {{
      if (autoTimer) clearInterval(autoTimer);
    }});
    hero.addEventListener('mouseleave', () => {{
      resetAuto();
    }});
  }}
}})();
</script>
"""

_HERO_HTML = _build_hero_html()
_HERO_IFRAME_HTML = _build_hero_iframe_html()
# iframe の高さ(60vh 相当の固定 px、Streamlit components.html の制約上 px 固定)
_HERO_HEIGHT_PX = 580


# ====================================================
# セクションバナー(ホームのコンテンツ入口)
# ====================================================
# 各バナー = タイトル + 説明 + 背景画像
_SECTION_BANNERS = [
    {
        "key": "diagnosis",
        "title": "診断する",
        "desc": "質問に答えてあなたに合う移住先を診断。",
        "image": "https://images.unsplash.com/photo-1603435580027-f30889418372?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&q=85&w=1600",
    },
    {
        "key": "map",
        "title": "地図で見る",
        "desc": "47都道府県をヒートマップ表示。",
        "image": "https://images.unsplash.com/photo-1754335073684-74d418954dd2?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&q=85&w=1600",
    },
    {
        "key": "ranking",
        "title": "ランキング",
        "desc": "全国住みやすさランキング。",
        "image": "https://images.unsplash.com/photo-1493976040374-85c8e12f0c0e?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&q=85&w=1600",
    },
    {
        "key": "compare",
        "title": "比較で見る",
        "desc": "気になる県をチャートで比較。",
        "image": "https://images.unsplash.com/photo-1504109586057-7a2ae83d1338?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&q=85&w=1600",
    },
    {
        "key": "detail",
        "title": "エリアを知る",
        "desc": "気になるエリアの詳細情報",
        "image": "https://images.unsplash.com/photo-1583937940470-b4b04ad42cf8?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&q=85&w=1600",
    },
    {
        "key": "model",
        "title": "AI 予測",
        "desc": "AI予測で3/5/10年後の未来を予測。",
        "image": "https://images.unsplash.com/photo-1708446637293-13b8dddbc97b?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&q=85&w=1600",
    },
]


def inject_global_css() -> None:
    """ページ冒頭で 1 回呼び出す. グローバル CSS を <style> として挿入."""
    st.markdown(_GLOBAL_CSS, unsafe_allow_html=True)


def render_hero() -> None:
    """ファストビューのヒーロー(4 枚スライドショー + 手動切替 + CTA).

    Streamlit の st.markdown は内部の <script> を実行しないため、
    スライドショー本体は components.html(iframe 描画).
    CTA「診断を始める」は iframe の sandbox 制約で親窓 navigate ができないため、
    メインページ側に出して負マージンでヒーロー上にオーバーレイ配置する.
    """
    components.html(_HERO_IFRAME_HTML, height=_HERO_HEIGHT_PX, scrolling=False)
    # iframe の外側 = メインページ. ここの <a> は通常のページ遷移として動作する.
    st.markdown(
        '<div class="movemap-hero-cta-row">'
        '<a href="?view=diagnosis" class="movemap-hero-cta-link">診断を始める</a>'
        '</div>',
        unsafe_allow_html=True,
    )


SECTION_KEYS = tuple(b["key"] for b in _SECTION_BANNERS)


def render_section_banners() -> str | None:
    """6 つのコンテンツ入口バナーをグリッド表示.

    バナー全体を `<a href="?view=KEY">` でラップし、画像クリックで遷移.
    Streamlit は URL クエリ変更を検知して再描画 → main.py の URL→state
    同期ロジックが view を切り替える.

    予備として下に Streamlit ボタンも配置(リンクが効かない環境向け).

    Returns:
        st.button がクリックされたら key、未クリックは None.
        (`<a>` クリックは URL 遷移なので戻り値とは無関係に動く)
    """
    chosen: str | None = None
    # クリッカブルバナー(画像 + テキスト + リンク遷移)
    grid_items = "".join(
        f'''<a href="?view={b['key']}" class="movemap-section-banner-visual"
                aria-label="{b['title']}" target="_self">
              <div class="movemap-section-banner-bg"
                   style="background-image: url('{b['image']}');"></div>
              <div class="movemap-section-banner-overlay"></div>
              <div class="movemap-section-banner-text">
                <div class="movemap-section-banner-title">{b['title']}</div>
                <div class="movemap-section-banner-desc">{b['desc']}</div>
                <div class="movemap-section-banner-cta">開く →</div>
              </div>
            </a>'''
        for b in _SECTION_BANNERS
    )
    st.markdown(
        f'<div class="movemap-section-grid">{grid_items}</div>',
        unsafe_allow_html=True,
    )
    # 予備:Streamlit ボタンによる遷移(リンクが効かない環境向け)
    with st.expander("または、ボタンで開く", expanded=False):
        for row_start in range(0, len(_SECTION_BANNERS), 2):
            cols = st.columns(2, gap="medium")
            for col_idx, b in enumerate(_SECTION_BANNERS[row_start:row_start + 2]):
                with cols[col_idx]:
                    if st.button(
                        f"▶ {b['title']}を開く",
                        key=f"home_open_{b['key']}",
                        use_container_width=True,
                        type="primary",
                    ):
                        chosen = b["key"]
    return chosen


def render_back_to_home_button() -> bool:
    """各セクション画面上部の「🏠 TOPページ」ボタン.

    `st.button` で確実にクリックを受け、呼び出し側で
    session_state["active_view"] を "home" に上書き + query_params を全クリア +
    st.rerun() でホーム画面を描画する.

    Returns:
        True: クリックされた(ホームに戻る処理を実行)
        False: 未クリック
    """
    return st.button(
        "🏠 TOPページ",
        key="back_to_home",
        type="secondary",
        help="ホーム画面に戻ります",
    )




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


def inject_ga4(measurement_id: str | None) -> None:
    """Google Analytics 4 のトラッキングタグを注入(設定時のみ).

    Streamlit は HTML を直接埋め込めないため `st.markdown(unsafe_allow_html=True)`
    で <script> を注入する. Streamlit はその script を iframe 内で実行するため
    ページビュー以外の細かな計測(ボタンクリック等)は別途 GA4 イベント送信が要.

    Args:
        measurement_id: G-XXXXXXXXXX 形式の Measurement ID.
            None または空文字なら何もしない(ローカル開発時のノイズ抑制).
    """
    if not measurement_id:
        return
    ga4_html = f"""
    <!-- Google tag (gtag.js) -->
    <script async src="https://www.googletagmanager.com/gtag/js?id={measurement_id}"></script>
    <script>
      window.dataLayer = window.dataLayer || [];
      function gtag(){{dataLayer.push(arguments);}}
      gtag('js', new Date());
      gtag('config', '{measurement_id}', {{
        'anonymize_ip': true,
        'send_page_view': true
      }});
    </script>
    """
    st.markdown(ga4_html, unsafe_allow_html=True)


__all__ = [
    "SECTION_KEYS",
    "inject_ga4",
    "inject_global_css",
    "render_back_to_home_button",
    "render_current_band",
    "render_hero",
    "render_mobile_hint",
    "render_section_banners",
    "render_tab_guide",
]
