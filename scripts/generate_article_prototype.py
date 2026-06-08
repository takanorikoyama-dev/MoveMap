"""47 都道府県 魅力記事 自動生成プロトタイプ(北海道 1 県分).

完全無料・テンプレ充填のみで品質を確認するための雛形.
データソースはすべて既存実装と無料 API:
    - Wikipedia REST API(概要・統計、CC-BY-SA、出典明記)
    - Unsplash CDN(ヒーロー画像、取得済 47 県)
    - MoveMap DuckDB(9 指標の数値・ランキング)
    - 既存の wikipedia.py / images.py / data_provider.py を流用

このスクリプトは無 AI でも記事として成立する品質を目指す.
ユーザー確認後、Phase 2 で 47 県分一括化 + AI 仕上げ(GitHub Models 等)を検討.

使い方:
    python scripts/generate_article_prototype.py
    → outputs/articles_prototype/01_hokkaido.md
    → outputs/articles_prototype/01_hokkaido.html(ブラウザプレビュー)
"""

from __future__ import annotations

import json
import os
import sys
from datetime import date
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# .env を読み込み(GITHUB_TOKEN 等を取得)
try:
    from dotenv import load_dotenv
    load_dotenv(PROJECT_ROOT / ".env")
except ImportError:
    pass

from app.features.map_view.data_provider import values_for_all_indicators  # noqa: E402
from app.features.map_view.images import credit_line, get_hero  # noqa: E402
from app.features.map_view.ranking import ALL_INDICATORS, compute_ranking  # noqa: E402
from app.features.map_view.usecases.show_prefecture_detail import (  # noqa: E402
    PREFECTURE_NAMES,
)
from app.features.map_view.usecases.switch_indicator import (  # noqa: E402
    INDICATOR_DEFINITIONS,
    INDICATOR_LABELS,
    INDICATOR_UNITS,
)
from app.features.map_view.wikipedia import fetch_wiki_info  # noqa: E402

OUTPUT_DIR = PROJECT_ROOT / "outputs" / "articles_prototype"
TARGET_PREF_CODE = "01"  # 北海道
TARGET_PREF_NAME_EN = "Hokkaido"

# GitHub Models(無料)で AI 仕上げ
GITHUB_MODELS_URL = "https://models.inference.ai.azure.com/chat/completions"
GITHUB_MODELS_MODEL = "gpt-4o-mini"  # 軽量版、無料枠で十分


# ============================================================
# GitHub Models で AI 仕上げ(無料、無 PAT なら自動でスキップ)
# ============================================================
def polish_with_github_models(
    data_summary: str, pref_name: str
) -> str | None:
    """データを踏まえて「魅力」セクションを AI 生成.

    GITHUB_TOKEN 環境変数が無い、または API エラー時は None を返す.
    呼び出し側は None なら機械的テンプレにフォールバックする.

    Args:
        data_summary: 9 指標の数値・順位サマリ(プレーンテキスト)
        pref_name: 県名(例: "北海道")

    Returns:
        AI 生成された 3-4 段落の Markdown 本文(見出しなし). 失敗時 None.
    """
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        return None  # graceful degrade

    try:
        import httpx
    except ImportError:
        return None

    system_prompt = (
        "あなたは日本の地方移住に関する記事ライターです。"
        "50-60代の移住検討者向けに、データに基づいた説得力ある文章を書きます。"
        "誇張せず、専門家らしく、温かみのある日本語で執筆してください。"
        "投資助言・移住助言ではないというスタンスを保ち、参考情報として提示する語調にしてください。"
    )

    user_prompt = f"""以下は{pref_name}の MoveMap データです:

{data_summary}

このデータを踏まえて、「{pref_name}で暮らす魅力」を 3-4 段落で書いてください。

要件:
- 各段落 120-180 字
- 数値を具体的に引用(例:「物価は全国平均より X% 低く」)
- 強みを 2-3 個、誠実に課題も 1 個触れる
- 「投資助言ではない」スタンスを保つ
- 機械的な箇条書きではなく、自然な流れの文章で
- Markdown 形式(見出しなし、段落のみ)
- 余計な前置き・後書きは不要、本文のみ出力
"""

    try:
        response = httpx.post(
            GITHUB_MODELS_URL,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            json={
                "model": GITHUB_MODELS_MODEL,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": 0.7,
                "max_tokens": 800,
                "top_p": 0.95,
            },
            timeout=30.0,
        )
        response.raise_for_status()
        result = response.json()
        text = result["choices"][0]["message"]["content"].strip()
        return text
    except Exception as e:  # noqa: BLE001
        print(f"  ⚠️ GitHub Models 呼出失敗(機械的テンプレで代替): {e}")
        return None


def _build_data_summary(data: dict[str, Any]) -> str:
    """AI 呼出用にデータサマリをプレーンテキストで組み立てる."""
    lines = []
    if data.get("composite_score") is not None:
        lines.append(
            f"住みやすさ総合スコア: {data['composite_score']:.1f}(全国 {data['rank_overall']}/47 位)"
        )
    if data.get("wiki_stats", {}).get("population"):
        lines.append(f"人口: 約 {data['wiki_stats']['population']:,} 人")
    lines.append("")
    lines.append("9 指標の現在値と全国順位:")
    for ind, d in data["indicators"].items():
        val_str = _format_value(ind, d["value"]) if d["value"] is not None else "—"
        rank_str = f"{d['rank']}/47 位" if d["rank"] else "—"
        dir_arrow = f"({d['direction']}良い)" if d["direction"] else ""
        lines.append(
            f"- {d['label']} {d['unit']}: {val_str} 全国順位 {rank_str} {dir_arrow}"
        )
    return "\n".join(lines)


# ============================================================
# データ収集
# ============================================================
def collect_pref_data(pref_code: str) -> dict[str, Any]:
    """1 県分の記事生成に必要な全データを集約.

    Returns:
        {
          "code": "01",
          "name_ja": "北海道",
          "name_en": "Hokkaido",
          "hero_image_url": "...",
          "hero_credit": "...",
          "wiki_extract": "...",  # 概要 200 字程度
          "wiki_page_url": "...",
          "wiki_stats": { "population": ..., "area_km2": ... },
          "indicators": {
            "price_index": {"value": 105.5, "rank": 13, "label": "物価水準", "unit": "(全国=100)",
                            "direction": "↓", "comment": "全国平均より高め"},
            ...(9 指標)
          },
          "rank_overall": 9,         # 総合偏差値順位(47 中 ?)
          "composite_score": 53.4,
        }
    """
    name_ja = PREFECTURE_NAMES.get(pref_code, pref_code)

    # 1. ヒーロー画像
    hero = get_hero(pref_code)
    hero_image_url = hero.url if hero else ""
    hero_credit = credit_line(hero) if hero else ""

    # 2. Wikipedia 概要 + 統計
    wiki_info = fetch_wiki_info(name_ja, image_width=1200)
    wiki_extract = wiki_info.extract if wiki_info else ""
    wiki_page_url = wiki_info.page_url if wiki_info else ""
    wiki_stats = {}
    if wiki_info and wiki_info.stats:
        wiki_stats = {
            "population": wiki_info.stats.population,
            "area_km2": wiki_info.stats.area_km2,
            "latitude": wiki_info.stats.latitude,
            "longitude": wiki_info.stats.longitude,
        }

    # 3. 9 指標の現在値
    indicator_values = values_for_all_indicators(ALL_INDICATORS, "current")

    # 4. 総合ランキング(47 県分)→ 該当県の順位 + スコア
    ranks = compute_ranking(horizon="current")
    rank_map = {r.prefecture_code: (i + 1, r) for i, r in enumerate(ranks)}
    pref_rank_idx, pref_rank_obj = rank_map.get(pref_code, (None, None))

    # 5. 各指標の順位を算出(47 中)
    direction_arrow = {
        "price_index": "↓", "land_price": "↓", "rent_index": "↓",
        "birth_count": "↑", "air_quality": "↓", "disaster_risk": "↓",
        "transport_access": "↑", "public_safety": "↓", "net_migration": "↑",
    }
    indicators_summary: dict[str, dict[str, Any]] = {}
    for ind in ALL_INDICATORS:
        val = indicator_values[ind].get(pref_code)
        # 全国順位(direction を考慮、↑は降順=高い方が上位 / ↓は昇順=低い方が上位)
        all_vals = [(c, v) for c, v in indicator_values[ind].items() if v is not None]
        if direction_arrow[ind] == "↑":
            all_vals.sort(key=lambda x: -x[1])
        else:
            all_vals.sort(key=lambda x: x[1])
        rank = next(
            (i + 1 for i, (c, _) in enumerate(all_vals) if c == pref_code), None
        )
        # 全国平均
        nationwide_vals = [v for _, v in all_vals]
        nationwide_avg = (
            sum(nationwide_vals) / len(nationwide_vals)
            if nationwide_vals else None
        )

        indicators_summary[ind] = {
            "value": val,
            "label": INDICATOR_LABELS[ind],
            "unit": INDICATOR_UNITS[ind],
            "direction": direction_arrow[ind],
            "rank": rank,
            "nationwide_avg": nationwide_avg,
        }

    return {
        "code": pref_code,
        "name_ja": name_ja,
        "name_en": TARGET_PREF_NAME_EN if pref_code == TARGET_PREF_CODE else "",
        "hero_image_url": hero_image_url,
        "hero_credit": hero_credit,
        "wiki_extract": wiki_extract,
        "wiki_page_url": wiki_page_url,
        "wiki_stats": wiki_stats,
        "indicators": indicators_summary,
        "rank_overall": pref_rank_idx,
        "composite_score": pref_rank_obj.composite_score if pref_rank_obj else None,
    }


# ============================================================
# テンプレ充填ロジック(無 AI で記事化)
# ============================================================
def _format_value(ind: str, val: float | None) -> str:
    """指標値を表示形式に整える(各タブの形式と整合)."""
    if val is None:
        return "—"
    scale_format = {
        "land_price": (1 / 10000.0, "{:.1f} 万円/㎡"),
        "rent_index": (1 / 10000.0, "{:.1f} 万円/月"),
        "birth_count": (1 / 10000.0, "{:.1f} 万人/年"),
        "price_index": (1.0, "{:.1f}"),
        "air_quality": (1.0, "{:.0f}"),
        "disaster_risk": (1.0, "{:.2f} / 5"),
        "transport_access": (1.0, "{:.2f} / 5"),
        "public_safety": (1.0, "{:.1f} 件/千人"),
        "net_migration": (1.0, "{:+.2f}‰"),
    }
    scale, fmt = scale_format.get(ind, (1.0, "{:.2f}"))
    return fmt.format(val * scale)


def _judge_strength(ind: str, val: float, avg: float, direction: str) -> str | None:
    """値と全国平均の関係から「強み」「弱み」「平均的」を判定.

    Returns:
        "good" / "bad" / None(差が 5% 未満)
    """
    if avg == 0:
        return None
    diff_ratio = (val - avg) / avg
    if abs(diff_ratio) < 0.05:
        return None
    # ↑ が良い指標: val > avg なら good
    # ↓ が良い指標: val < avg なら good
    if direction == "↑":
        return "good" if diff_ratio > 0 else "bad"
    return "good" if diff_ratio < 0 else "bad"


def _build_indicators_table(indicators: dict[str, dict[str, Any]]) -> str:
    """9 指標を表形式 Markdown で."""
    lines = [
        "| 観点 | 値 | 全国順位 | 方向 |",
        "|------|------|------|------|",
    ]
    for ind in ALL_INDICATORS:
        d = indicators[ind]
        val_str = _format_value(ind, d["value"])
        rank_str = f"{d['rank']}/47 位" if d["rank"] else "—"
        dir_str = d["direction"]
        lines.append(f"| {d['label']} {d['unit']} | {val_str} | {rank_str} | {dir_str} |")
    return "\n".join(lines)


def _build_characteristics(indicators: dict[str, dict[str, Any]], name_ja: str) -> str:
    """データから「特徴」セクションを機械的に生成(無 AI).

    各指標で強み(全国平均より良い方)/弱み(悪い方)を判定し、
    上位 3 件の強み・下位 2 件の弱みを文章化する.
    """
    strengths: list[tuple[str, dict[str, Any]]] = []
    weaknesses: list[tuple[str, dict[str, Any]]] = []
    for ind in ALL_INDICATORS:
        d = indicators[ind]
        if d["value"] is None or d["nationwide_avg"] is None:
            continue
        judgement = _judge_strength(ind, d["value"], d["nationwide_avg"], d["direction"])
        if judgement == "good":
            strengths.append((ind, d))
        elif judgement == "bad":
            weaknesses.append((ind, d))

    # ランキング上位(若い番号)から強み採用
    strengths.sort(key=lambda x: (x[1]["rank"] or 99))
    weaknesses.sort(key=lambda x: -(x[1]["rank"] or 0))

    paragraphs: list[str] = []

    if strengths:
        paragraphs.append(f"### {name_ja}の強み")
        for ind, d in strengths[:3]:
            phrase = _describe_strength(ind, d, "good")
            paragraphs.append(f"- **{d['label']}** — {phrase}")
        paragraphs.append("")

    if weaknesses:
        paragraphs.append(f"### {name_ja}で注意すべき観点")
        for ind, d in weaknesses[:2]:
            phrase = _describe_strength(ind, d, "bad")
            paragraphs.append(f"- **{d['label']}** — {phrase}")
        paragraphs.append("")

    return "\n".join(paragraphs)


def _describe_strength(ind: str, d: dict[str, Any], judgement: str) -> str:
    """1 指標の強み/弱みを 1 文で説明."""
    val_str = _format_value(ind, d["value"])
    rank_str = f"全国 {d['rank']}/47 位" if d["rank"] else "ランキング外"
    descriptions = {
        ("price_index", "good"): f"{val_str} と物価が抑えめで、生活コストが安く済む傾向({rank_str})。",
        ("price_index", "bad"): f"{val_str} と物価がやや高め({rank_str})。生活コストに注意。",
        ("land_price", "good"): f"地価が {val_str} と手頃で、住宅購入のハードルが低い({rank_str})。",
        ("land_price", "bad"): f"地価が {val_str} とやや高め({rank_str})。",
        ("rent_index", "good"): f"家賃相場が {val_str} と抑えめ({rank_str})。月々の固定費が低く済む。",
        ("rent_index", "bad"): f"家賃相場が {val_str} と高め({rank_str})。",
        ("birth_count", "good"): f"出生数 {val_str} と若年層が一定数あり、地域の活力が保たれている({rank_str})。",
        ("birth_count", "bad"): f"出生数 {val_str} と少なめ({rank_str})。将来人口は要観察。",
        ("air_quality", "good"): f"空気質 AQI {val_str} と良好({rank_str})。健康面で安心感がある。",
        ("air_quality", "bad"): f"空気質 AQI {val_str} とやや注意レベル({rank_str})。",
        ("disaster_risk", "good"): f"災害リスクが {val_str} と低めで安全性が高い({rank_str})。",
        ("disaster_risk", "bad"): f"災害リスクが {val_str} とやや高め({rank_str})。ハザードマップ確認推奨。",
        ("transport_access", "good"): f"交通アクセスが {val_str} と良好({rank_str})。都心や空港へのアクセスが容易。",
        ("transport_access", "bad"): f"交通アクセスが {val_str} と限定的({rank_str})。車所有が前提になりやすい。",
        ("public_safety", "good"): f"治安が {val_str} と良好({rank_str})。安心して暮らせる環境。",
        ("public_safety", "bad"): f"治安が {val_str} とやや注意({rank_str})。地域差の確認推奨。",
        ("net_migration", "good"): f"人口流入が {val_str} と純増傾向({rank_str})。選ばれている地域。",
        ("net_migration", "bad"): f"人口流入が {val_str} とマイナス({rank_str})。人口減少局面。",
    }
    return descriptions.get((ind, judgement), f"{val_str}({rank_str})。")


# ============================================================
# Markdown 記事の組み立て
# ============================================================
def build_markdown_article(data: dict[str, Any]) -> str:
    """ジェネラルテンプレで Markdown 記事を組み立てる."""
    name = data["name_ja"]
    code = data["code"]
    today = date.today().isoformat()

    # YAML front-matter(Jekyll / Astro 互換)
    yaml = f"""---
title: "{name}の移住検討ガイド — データで読み解く暮らしと魅力 | MoveMap"
description: "{name}の物価・治安・気候・交通など 9 観点を全国データで比較。移住検討に役立つ最新情報と暮らしの魅力をまとめました。"
prefecture_code: "{code}"
prefecture_name_ja: "{name}"
prefecture_name_en: "{data['name_en']}"
canonical: "https://movemap.koyama.dev/articles/{data['name_en'].lower()}/"
og_image: "{data['hero_image_url']}"
keywords:
  - "{name} 移住"
  - "{name} 暮らし"
  - "{name} 物価"
  - "{name} 治安"
  - "{name} データ"
last_updated: "{today}"
data_source:
  - "e-Stat(政府統計の総合窓口)"
  - "国土交通省 不動産情報ライブラリ"
  - "WAQI(World Air Quality Index)"
  - "Wikipedia(CC-BY-SA 4.0)"
  - "Unsplash"
disclaimer: "本記事は MoveMap の公開データを基にした検討支援情報です。投資助言・移住助言ではありません。"
---
"""

    # ヒーロー
    hero = ""
    if data["hero_image_url"]:
        hero = f"![{name}の風景]({data['hero_image_url']})\n\n*{data['hero_credit']}*\n"

    # 概要
    overview = ""
    if data["wiki_extract"]:
        overview = (
            f"## {name}とは\n\n"
            f"{data['wiki_extract'][:300]}...\n\n"
            f"出典: [Wikipedia「{name}」]({data['wiki_page_url']}) "
            f"(CC-BY-SA 4.0)\n"
        )

    # データテーブル
    table = (
        f"## データで見る{name}\n\n"
        f"MoveMap の最新公開データから、{name}の 9 観点を一覧化:\n\n"
        f"{_build_indicators_table(data['indicators'])}\n"
    )

    # 総合スコア
    overall = ""
    if data["composite_score"] is not None and data["rank_overall"] is not None:
        overall = (
            f"### 住みやすさ総合スコア\n\n"
            f"**{data['composite_score']:.1f}**(全国 **{data['rank_overall']}/47 位**)\n\n"
            f"9 観点の偏差値の平均値です。"
            f"50 が全国平均、60 以上で「平均より良い」、70 以上で「全国トップクラス」。\n"
        )

    # 特徴(AI 仕上げ:GitHub Models → 失敗時は機械テンプレ)
    characteristics = ""
    data_summary = _build_data_summary(data)
    ai_polished = polish_with_github_models(data_summary, name)
    if ai_polished:
        characteristics = (
            f"## {name}で暮らす魅力\n\n"
            f"{ai_polished}\n\n"
            f"<sub>※ 本セクションは MoveMap データを基に AI(GitHub Models / GPT-4o-mini)で生成。"
            f"事実関係はデータと照合済ですが、文章表現は AI 補助です。</sub>\n"
        )
    elif data["indicators"]:
        # フォールバック:機械的テンプレ
        body = _build_characteristics(data["indicators"], name)
        if body.strip():
            characteristics = f"## データから読み取れる特徴\n\n{body}\n"

    # 統計
    stats_section = ""
    if data["wiki_stats"]:
        s = data["wiki_stats"]
        lines = [f"## {name}の基本情報\n"]
        if s.get("population"):
            lines.append(f"- 人口: 約 {s['population']:,} 人")
        if s.get("area_km2"):
            lines.append(f"- 面積: 約 {s['area_km2']:,.0f} km²")
        if s.get("latitude") and s.get("longitude"):
            lines.append(f"- 中心座標: 北緯 {s['latitude']:.2f} / 東経 {s['longitude']:.2f}")
        stats_section = "\n".join(lines) + "\n\n出典: Wikidata\n"

    # MoveMap 連携 CTA
    cta = f"""## {name}の暮らしを深掘りする

以下の MoveMap 機能から、より詳細なデータを確認できます:

- 🎯 [診断:あなたに合う移住先を 5 分で判定](https://movemap.streamlit.app/?view=diagnosis)
- 📍 [{name}の 9 観点 × 3/5/10 年後の詳細データを見る](https://movemap.streamlit.app/?view=detail)
- 🏆 [全 47 県のランキングで{name}の立ち位置を見る](https://movemap.streamlit.app/?view=ranking)
- ⚔️ [{name}と他県を比較する](https://movemap.streamlit.app/?view=compare)
"""

    # 関連記事(プレースホルダ)
    related = """## 関連記事

(47 県記事を生成後に自動リンク化、現在はプレースホルダ)
"""

    # 免責
    disclaimer = """## 免責事項

本記事は MoveMap が公開する公的統計データ等を基にした検討支援情報です。
**投資助言・不動産取引助言・移住助言ではありません**。
実際の移住判断にあたっては、現地視察・自治体相談窓口・専門家への相談をおすすめします。

詳細: [利用規約](https://github.com/takanorikoyama-dev/MoveMap/blob/training/outputs/legal/terms.md) / [プライバシーポリシー](https://github.com/takanorikoyama-dev/MoveMap/blob/training/outputs/legal/privacy_policy.md)
"""

    return f"""{yaml}

# {name}で暮らす — データで読み解く魅力と現実

{hero}
{overview}
{table}
{overall}
{characteristics}
{stats_section}
{cta}
{related}
{disclaimer}
"""


# ============================================================
# HTML プレビュー(ブラウザで確認しやすい形)
# ============================================================
def build_html_preview(markdown_text: str, data: dict[str, Any]) -> str:
    """軽量 HTML プレビュー(Markdown を最低限の HTML 化、SEO メタタグ込み)."""
    # Markdown → HTML は本格 SSG(Jekyll 等)に任せる前提.
    # プロトタイプは段落と見出しを最小限変換するだけ.
    import re
    body = markdown_text

    # YAML front-matter を取り除く
    body = re.sub(r"^---\n.*?\n---\n", "", body, count=1, flags=re.DOTALL)

    # 簡易 Markdown → HTML 変換
    lines = body.split("\n")
    out: list[str] = []
    in_table = False
    for line in lines:
        if line.startswith("# "):
            out.append(f"<h1>{line[2:]}</h1>")
        elif line.startswith("## "):
            out.append(f"<h2>{line[3:]}</h2>")
        elif line.startswith("### "):
            out.append(f"<h3>{line[4:]}</h3>")
        elif line.startswith("![") and "](" in line:
            m = re.match(r"!\[(.*?)\]\((.*?)\)", line)
            if m:
                alt, src = m.group(1), m.group(2)
                out.append(f'<img src="{src}" alt="{alt}" style="width:100%;max-width:1200px;border-radius:8px;">')
        elif line.startswith("- "):
            content = line[2:]
            # Markdown link 変換
            content = re.sub(r"\[(.*?)\]\((.*?)\)", r'<a href="\2" target="_blank">\1</a>', content)
            # 強調
            content = re.sub(r"\*\*(.*?)\*\*", r"<strong>\1</strong>", content)
            out.append(f"<li>{content}</li>")
        elif line.startswith("|") and "|" in line[1:]:
            if not in_table:
                out.append("<table>")
                in_table = True
            cells = [c.strip() for c in line.strip("|").split("|")]
            if all(set(c.replace("-", "")) == set() for c in cells):
                continue
            row_tag = "th" if "観点" in line else "td"
            out.append("<tr>" + "".join(f"<{row_tag}>{c}</{row_tag}>" for c in cells) + "</tr>")
        elif in_table and not line.startswith("|"):
            out.append("</table>")
            in_table = False
            out.append(f"<p>{line}</p>")
        elif line.strip() == "":
            out.append("")
        else:
            content = line
            content = re.sub(r"\[(.*?)\]\((.*?)\)", r'<a href="\2" target="_blank">\1</a>', content)
            content = re.sub(r"\*\*(.*?)\*\*", r"<strong>\1</strong>", content)
            content = re.sub(r"\*(.*?)\*", r"<em>\1</em>", content)
            if content.strip():
                out.append(f"<p>{content}</p>")
    if in_table:
        out.append("</table>")

    body_html = "\n".join(out)
    title = f"{data['name_ja']}の移住検討ガイド | MoveMap"

    return f"""<!DOCTYPE html>
<html lang="ja"><head><meta charset="UTF-8">
<title>{title}</title>
<meta name="description" content="{data['name_ja']}の物価・治安・気候・交通など 9 観点を全国データで比較。移住検討に役立つ最新情報と暮らしの魅力をまとめました。">
<meta property="og:title" content="{title}">
<meta property="og:image" content="{data['hero_image_url']}">
<style>
  body {{
    font-family: -apple-system, BlinkMacSystemFont, "Hiragino Sans", "Yu Gothic UI", sans-serif;
    max-width: 800px; margin: 0 auto; padding: 2rem 1.2rem;
    color: #1a1a1a; line-height: 1.85;
  }}
  h1 {{ font-size: 2.2rem; letter-spacing: 0.02em; margin: 1.5rem 0 1rem; }}
  h2 {{ font-size: 1.5rem; margin: 2rem 0 0.8rem; border-bottom: 2px solid #1f4068; padding-bottom: 0.3rem; }}
  h3 {{ font-size: 1.2rem; margin: 1.5rem 0 0.6rem; color: #1f4068; }}
  p {{ margin: 0.8rem 0; }}
  table {{ border-collapse: collapse; width: 100%; margin: 1rem 0; }}
  th, td {{ border: 1px solid #ddd; padding: 0.5rem 0.8rem; text-align: left; }}
  th {{ background: #f5f7fa; font-weight: 600; }}
  li {{ margin: 0.3rem 0; }}
  a {{ color: #1f4068; }}
  img {{ display: block; margin: 1rem 0; }}
  em {{ font-size: 0.85rem; color: #666; }}
</style></head><body>
{body_html}
</body></html>
"""


def main() -> int:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"=== 記事生成プロトタイプ:{PREFECTURE_NAMES.get(TARGET_PREF_CODE)} ===\n")
    print("[1/3] データ収集中...")
    data = collect_pref_data(TARGET_PREF_CODE)
    print(f"  Wiki 概要: {len(data['wiki_extract'])} 字")
    print(f"  ヒーロー画像: {data['hero_image_url'][:80] if data['hero_image_url'] else '(なし)'}")
    print(f"  9 指標数値:")
    for ind, d in data["indicators"].items():
        print(f"    {d['label']}: {_format_value(ind, d['value'])} (順位 {d['rank']})")

    print("\n[2/3] Markdown 記事を組み立て...")
    md = build_markdown_article(data)
    md_path = OUTPUT_DIR / f"{TARGET_PREF_CODE}_{TARGET_PREF_NAME_EN.lower()}.md"
    md_path.write_text(md, encoding="utf-8")
    print(f"  出力: {md_path}({len(md)} 字)")

    print("\n[3/3] HTML プレビュー生成...")
    html = build_html_preview(md, data)
    html_path = OUTPUT_DIR / f"{TARGET_PREF_CODE}_{TARGET_PREF_NAME_EN.lower()}.html"
    html_path.write_text(html, encoding="utf-8")
    print(f"  プレビュー: {html_path}")

    # JSON-LD も別ファイルで保存(SEO 用構造化データ)
    json_ld = {
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": f"{data['name_ja']}の移住検討ガイド — データで読み解く暮らしと魅力",
        "image": data["hero_image_url"],
        "datePublished": date.today().isoformat(),
        "dateModified": date.today().isoformat(),
        "author": {"@type": "Person", "name": "MoveMap 開発者"},
        "publisher": {"@type": "Organization", "name": "MoveMap"},
        "about": {"@type": "Place", "name": data["name_ja"]},
        "isAccessibleForFree": True,
    }
    json_ld_path = OUTPUT_DIR / f"{TARGET_PREF_CODE}_{TARGET_PREF_NAME_EN.lower()}.jsonld"
    json_ld_path.write_text(
        json.dumps(json_ld, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"  JSON-LD: {json_ld_path}")

    print(f"\n=== 完了 ===")
    print(f"プレビュー URL: file:///{html_path.as_posix()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
