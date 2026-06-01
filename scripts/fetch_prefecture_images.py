"""47 都道府県の代表画像を Unsplash + Wikimedia から取得する.

DEC-016(mode C 公開)後の Apple 風ビジュアル刷新に向け、各県のヒーロー画像と
ギャラリー画像を CDN 直リンクで取得し、`seeds/prefecture_images.json` に保存する.

優先順位:
    1. ヒーロー画像: Unsplash(キーあれば)→ Wikimedia フォールバック
    2. ギャラリー: Wikimedia(常に取得)

特徴:
    - 画像本体はダウンロードしない(CDN 直リンク参照のみ、Streamlit Cloud 軽量化)
    - 再実行で既存結果をマージ(--force で全件再取得)
    - Unsplash キー未設定でも動作(Wikimedia のみで代替)

使い方:
    UNSPLASH_ACCESS_KEY=xxx python scripts/fetch_prefecture_images.py        # 通常
    python scripts/fetch_prefecture_images.py --only 13,01,29                # 特定県のみ
    python scripts/fetch_prefecture_images.py --force                        # 既存無視で再取得
    python scripts/fetch_prefecture_images.py --preview                      # HTML プレビュー再生成のみ

ライセンス:
    Unsplash: Unsplash License(改変・商用 OK、クレジット推奨)
    Wikimedia: CC-BY-SA 4.0(クレジット必須、UI フッターに明示)
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.features.map_view.wikipedia import fetch_wiki_info  # noqa: E402
from app.shared.config import load_config  # noqa: E402
from app.shared.http_client import HttpRetryExhausted, get_json  # noqa: E402
from app.shared.logger import get_logger  # noqa: E402

logger = get_logger(__name__)

UNSPLASH_BASE = "https://api.unsplash.com/search/photos"
USER_AGENT = "MoveMap/0.1 (image fetcher)"

OUTPUT_JSON = PROJECT_ROOT / "seeds" / "prefecture_images.json"
OUTPUT_HTML = PROJECT_ROOT / "seeds" / "prefecture_images.html"
OUTPUT_CREDITS = PROJECT_ROOT / "seeds" / "image_credits.md"
OVERRIDES_PATH = PROJECT_ROOT / "seeds" / "prefecture_image_overrides.json"


def load_query_overrides() -> dict[str, str]:
    """県別 Unsplash クエリ上書きを読み込む(`_` プレフィックス行はメタ).

    Returns:
        {pref_code: query_string} の辞書.
    """
    if not OVERRIDES_PATH.exists():
        return {}
    try:
        data = json.loads(OVERRIDES_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return {
        code: entry.get("query", "")
        for code, entry in data.items()
        if not code.startswith("_") and isinstance(entry, dict) and entry.get("query")
    }


def load_prefectures() -> list[dict[str, str]]:
    """seeds/prefectures.csv から 47 都道府県を読み込む."""
    path = PROJECT_ROOT / "seeds" / "prefectures.csv"
    rows: list[dict[str, str]] = []
    with path.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    return rows


def search_unsplash(name_en: str, access_key: str, override_query: str = "") -> dict[str, Any] | None:
    """Unsplash で都道府県名検索. 失敗時 None.

    Args:
        name_en: 県の英名(デフォルトクエリ生成に使用).
        access_key: Unsplash Access Key.
        override_query: 指定があればこちらを優先(自然系などへの調整用).

    Returns:
        最初の結果(landscape orientation, 関連度順).
    """
    query = override_query or f"{name_en} Japan"
    try:
        payload = get_json(
            UNSPLASH_BASE,
            params={
                "query": query,
                "orientation": "landscape",
                "per_page": "3",
                "content_filter": "high",
            },
            headers={
                "Authorization": f"Client-ID {access_key}",
                "Accept-Version": "v1",
                "User-Agent": USER_AGENT,
            },
        )
    except HttpRetryExhausted:
        logger.warning(f"Unsplash 取得失敗: {query}")
        return None

    results = payload.get("results") or []
    if not results:
        return None
    return results[0] if isinstance(results[0], dict) else None


def build_unsplash_image_ref(result: dict[str, Any]) -> dict[str, str]:
    """Unsplash の結果から保存用 ImageRef を組み立てる."""
    user = result.get("user") or {}
    urls = result.get("urls") or {}
    return {
        "url": urls.get("regular") or urls.get("small") or "",
        "thumb_url": urls.get("small") or urls.get("thumb") or "",
        "source": "unsplash",
        "photographer": str(user.get("name") or "Unknown"),
        "photographer_url": str(user.get("links", {}).get("html") or ""),
        "license": "Unsplash License",
        "license_url": "https://unsplash.com/license",
        "description": str(result.get("alt_description") or result.get("description") or ""),
        "source_url": str(result.get("links", {}).get("html") or ""),
    }


def build_wikimedia_hero_ref(wiki_info: Any) -> dict[str, str]:
    """Wikipedia から取得した代表画像を ImageRef に."""
    return {
        "url": wiki_info.image_url or "",
        "thumb_url": wiki_info.image_url or "",  # Wikimedia は thumbnail サイズ指定済み
        "source": "wikimedia",
        "photographer": "Wikimedia Commons contributor",
        "photographer_url": wiki_info.page_url,
        "license": "CC-BY-SA 4.0",
        "license_url": "https://creativecommons.org/licenses/by-sa/4.0/",
        "description": (wiki_info.extract[:120] if wiki_info.extract else ""),
        "source_url": wiki_info.page_url,
    }


def build_wikimedia_gallery_ref(url: str, wiki_info: Any) -> dict[str, str]:
    return {
        "url": url,
        "thumb_url": url,
        "source": "wikimedia",
        "photographer": "Wikimedia Commons contributor",
        "photographer_url": wiki_info.page_url,
        "license": "CC-BY-SA 4.0",
        "license_url": "https://creativecommons.org/licenses/by-sa/4.0/",
        "description": "",
        "source_url": wiki_info.page_url,
    }


def fetch_for_prefecture(
    code: str,
    name_ja: str,
    name_en: str,
    unsplash_key: str | None,
    query_override: str = "",
) -> dict[str, Any]:
    """1 県分の hero + gallery を取得."""
    record: dict[str, Any] = {
        "code": code,
        "name_ja": name_ja,
        "name_en": name_en,
        "hero": None,
        "gallery": [],
        "status": "ok",
    }

    # Step 1: Wikimedia(常に取得 — ギャラリーと extract のため)
    wiki_info = fetch_wiki_info(name_ja, image_width=1200, gallery_limit=4)
    if wiki_info is None:
        logger.warning(f"[{code}] {name_ja}: Wikipedia 取得失敗")
        record["status"] = "wiki_failed"
    else:
        # Wikimedia のヒーロー候補(Unsplash が無ければこれを使う)
        wiki_hero = build_wikimedia_hero_ref(wiki_info) if wiki_info.image_url else None
        # ギャラリーは常に Wikimedia から
        for g_url in wiki_info.gallery_urls:
            record["gallery"].append(build_wikimedia_gallery_ref(g_url, wiki_info))
        record["_wiki_hero_fallback"] = wiki_hero
        record["_wiki_extract"] = wiki_info.extract[:200] if wiki_info.extract else ""

    # Step 2: Unsplash でヒーロー上書き(キーあれば)
    if unsplash_key:
        u_result = search_unsplash(name_en, unsplash_key, override_query=query_override)
        if u_result:
            record["hero"] = build_unsplash_image_ref(u_result)
            if query_override:
                record["hero"]["query_used"] = query_override
            tag = "(override)" if query_override else ""
            logger.info(f"[{code}] {name_ja}: Unsplash ヒーロー取得 {tag}")

    # Step 3: Unsplash が無ければ Wikimedia ヒーローにフォールバック
    if record["hero"] is None and record.get("_wiki_hero_fallback"):
        record["hero"] = record["_wiki_hero_fallback"]
        logger.info(f"[{code}] {name_ja}: Wikimedia ヒーローを採用")

    # 内部 _ プレフィックスを除去
    record.pop("_wiki_hero_fallback", None)
    return record


def load_existing() -> dict[str, dict[str, Any]]:
    if not OUTPUT_JSON.exists():
        return {}
    try:
        payload = json.loads(OUTPUT_JSON.read_text(encoding="utf-8"))
        items = payload.get("prefectures") or []
        return {item["code"]: item for item in items if isinstance(item, dict)}
    except json.JSONDecodeError:
        return {}


def save_json(records: dict[str, dict[str, Any]], unsplash_used: bool) -> None:
    sorted_recs = [records[k] for k in sorted(records.keys())]
    payload = {
        "version": 1,
        "generated_by": "scripts/fetch_prefecture_images.py",
        "sources_used": ["wikimedia"] + (["unsplash"] if unsplash_used else []),
        "license_summary": {
            "unsplash": "Unsplash License — 改変・商用 OK、クレジット推奨",
            "wikimedia": "CC-BY-SA 4.0 — クレジット必須",
        },
        "prefectures": sorted_recs,
    }
    OUTPUT_JSON.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    logger.info(f"JSON 出力: {OUTPUT_JSON}")


def save_credits_md(records: dict[str, dict[str, Any]]) -> None:
    """INV-BIZ-008 対応:画像クレジットを 1 つの Markdown に集約."""
    lines = [
        "# 画像クレジット一覧",
        "",
        "MoveMap で使用する 47 都道府県の画像クレジット(DEC-016 / INV-BIZ-008 対応).",
        "",
        "## ライセンス概要",
        "",
        "- **Unsplash License**: 改変・商用 OK、クレジット推奨",
        "- **CC-BY-SA 4.0 (Wikimedia Commons)**: クレジット必須、改変時は同一ライセンスで公開",
        "",
        "## 県別クレジット",
        "",
        "| 県 | ソース | クレジット | ライセンス |",
        "|---|---|---|---|",
    ]
    for code in sorted(records.keys()):
        rec = records[code]
        hero = rec.get("hero") or {}
        src = hero.get("source") or "—"
        photo = hero.get("photographer") or "—"
        url = hero.get("photographer_url") or hero.get("source_url") or ""
        lic = hero.get("license") or "—"
        cred_text = f"[{photo}]({url})" if url else photo
        lines.append(f"| [{code}] {rec.get('name_ja')} | {src} | {cred_text} | {lic} |")
    lines.append("")
    OUTPUT_CREDITS.write_text("\n".join(lines), encoding="utf-8")
    logger.info(f"クレジット: {OUTPUT_CREDITS}")


def save_html_preview(records: dict[str, dict[str, Any]]) -> None:
    """Apple 風レイアウトの HTML プレビューを生成."""
    sorted_recs = [records[k] for k in sorted(records.keys())]
    total = len(sorted_recs)
    has_hero = sum(1 for r in sorted_recs if (r.get("hero") or {}).get("url"))
    has_unsplash = sum(1 for r in sorted_recs if (r.get("hero") or {}).get("source") == "unsplash")

    html: list[str] = [
        "<!DOCTYPE html><html lang='ja'><head><meta charset='utf-8'>",
        "<title>47 都道府県 ヒーロー画像</title>",
        "<style>",
        "* { box-sizing: border-box; margin: 0; padding: 0; }",
        "body {",
        "  font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Display',",
        "    'Hiragino Sans', 'ヒラギノ角ゴ ProN', 'Yu Gothic UI', sans-serif;",
        "  background: #ffffff; color: #1d1d1f; line-height: 1.47;",
        "  padding: 0 0 6rem 0;",
        "}",
        "header {",
        "  text-align: center; padding: 4rem 1rem 2.5rem;",
        "  border-bottom: 1px solid #f5f5f7;",
        "}",
        "header h1 { font-size: 3rem; font-weight: 700; letter-spacing: -0.025em; }",
        "header .stat { color: #6e6e73; margin-top: 1rem; font-size: 1.1rem; }",
        "header .stat strong { color: #1d1d1f; font-variant: tabular-nums; }",
        ".grid {",
        "  max-width: 1180px; margin: 4rem auto; padding: 0 1.5rem;",
        "  display: grid; grid-template-columns: 1fr 1fr; gap: 2.5rem;",
        "}",
        "@media (max-width: 780px) { .grid { grid-template-columns: 1fr; gap: 2rem; } }",
        ".card { display: flex; flex-direction: column; }",
        ".card .hero {",
        "  width: 100%; aspect-ratio: 16/10; object-fit: cover;",
        "  background: #f5f5f7; border-radius: 18px;",
        "}",
        ".card .meta {",
        "  display: flex; align-items: baseline; gap: 0.8rem;",
        "  margin: 1.2rem 0 0.5rem;",
        "}",
        ".card .code {",
        "  color: #6e6e73; font-size: 0.9rem; font-variant: tabular-nums;",
        "}",
        ".card .name { font-size: 1.5rem; font-weight: 600; letter-spacing: -0.015em; }",
        ".card .src {",
        "  margin-left: auto; padding: 0.2rem 0.6rem; font-size: 0.78rem;",
        "  border-radius: 999px; background: #f5f5f7; color: #6e6e73;",
        "  font-weight: 500;",
        "}",
        ".card .src.unsplash { background: #0071e3; color: #ffffff; }",
        ".card .credit { font-size: 0.82rem; color: #6e6e73; margin-top: 0.4rem; }",
        ".card .credit a { color: #0071e3; text-decoration: none; }",
        ".card .credit a:hover { text-decoration: underline; }",
        ".card .desc { font-size: 0.95rem; color: #424245; margin-top: 0.6rem; }",
        ".card .gallery {",
        "  display: grid; grid-template-columns: repeat(4, 1fr); gap: 0.6rem;",
        "  margin-top: 0.8rem;",
        "}",
        ".card .gallery img {",
        "  width: 100%; aspect-ratio: 1/1; object-fit: cover;",
        "  background: #f5f5f7; border-radius: 8px;",
        "}",
        "</style></head><body>",
        "<header>",
        "<h1>47 都道府県、データで。</h1>",
        f'<p class="stat">'
        f"取得済 <strong>{total}</strong> 県　／"
        f" ヒーロー画像 <strong>{has_hero}</strong>　／"
        f" Unsplash 採用 <strong>{has_unsplash}</strong></p>",
        "</header>",
        '<div class="grid">',
    ]
    for r in sorted_recs:
        hero = r.get("hero") or {}
        hero_url = hero.get("url") or ""
        src = hero.get("source") or ""
        photo = hero.get("photographer") or ""
        photo_url = hero.get("photographer_url") or ""
        license_name = hero.get("license") or ""
        desc = hero.get("description") or r.get("_wiki_extract", "") or ""
        gallery = r.get("gallery") or []

        gallery_html = ""
        if isinstance(gallery, list):
            gallery_html = "".join(
                f'<a href="{(g or {}).get("url","")}" target="_blank">'
                f'<img src="{(g or {}).get("url","")}" loading="lazy"></a>'
                for g in gallery
            )

        html.append(f'<article class="card">')
        if hero_url:
            html.append(
                f'<a href="{hero_url}" target="_blank">'
                f'<img class="hero" src="{hero_url}" loading="lazy"></a>'
            )
        else:
            html.append('<div class="hero"></div>')
        html.append(
            f'<div class="meta">'
            f'<span class="code">[{r.get("code","")}]</span>'
            f'<span class="name">{r.get("name_ja","")}</span>'
            f'<span class="src {src}">{src or "—"}</span>'
            f"</div>"
        )
        if desc:
            html.append(f'<p class="desc">{desc[:140]}{"…" if len(desc) > 140 else ""}</p>')
        credit_html = (
            f'<a href="{photo_url}" target="_blank">{photo}</a> ／ {license_name}'
            if photo_url
            else f"{photo} ／ {license_name}"
        )
        html.append(f'<p class="credit">{credit_html}</p>')
        if gallery_html:
            html.append(f'<div class="gallery">{gallery_html}</div>')
        html.append("</article>")
    html.append("</div></body></html>")
    OUTPUT_HTML.write_text("\n".join(html), encoding="utf-8")
    logger.info(f"HTML プレビュー: {OUTPUT_HTML}")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--only", type=str, default="", help="取得する県コード(カンマ区切り、例: 13,01)")
    p.add_argument("--force", action="store_true", help="既存結果を無視して再取得")
    p.add_argument(
        "--preview",
        action="store_true",
        help="既存 JSON から HTML プレビューだけ再生成",
    )
    return p.parse_args()


def main() -> int:
    args = parse_args()
    cfg = load_config()
    existing = load_existing()

    if args.preview:
        if not existing:
            print("既存 JSON がありません。先に通常実行してください。", file=sys.stderr)
            return 1
        save_html_preview(existing)
        save_credits_md(existing)
        print("HTML / クレジット を再生成しました")
        return 0

    prefs = load_prefectures()
    only_codes = set(c.strip() for c in args.only.split(",") if c.strip())
    if only_codes:
        prefs = [p for p in prefs if p["code"] in only_codes]
        print(f"対象: {len(prefs)} 県(--only 指定)")

    if cfg.unsplash_access_key:
        print("Unsplash モード: ON(キー検出)")
    else:
        print("Unsplash モード: OFF(UNSPLASH_ACCESS_KEY 未設定 → Wikimedia のみ)")

    overrides = load_query_overrides()
    if overrides:
        print(f"クエリ上書き: {len(overrides)} 件 ({list(overrides.keys())})")

    # --force と --only を併用する場合、既存はキープしつつ対象だけ再取得する.
    # --force のみ(--only なし)は全て破棄して再取得する.
    if args.force and not only_codes:
        records: dict[str, dict[str, Any]] = {}
    else:
        records = dict(existing)
    fetched = 0
    skipped = 0
    for row in prefs:
        code = row["code"]
        if code in records and not args.force and not only_codes:
            skipped += 1
            continue
        record = fetch_for_prefecture(
            code=code,
            name_ja=row["name_ja"],
            name_en=row["name_en"],
            unsplash_key=cfg.unsplash_access_key,
            query_override=overrides.get(code, ""),
        )
        records[code] = record
        fetched += 1
        hero_src = (record.get("hero") or {}).get("source", "—")
        print(f"  [{code}] {row['name_ja']:6s} -> ヒーロー: {hero_src:9s}　ギャラリー: {len(record.get('gallery') or [])} 枚")

    save_json(records, unsplash_used=bool(cfg.unsplash_access_key))
    save_credits_md(records)
    save_html_preview(records)

    print(f"\n取得: {fetched} 件 / スキップ(キャッシュ): {skipped} 件")
    print(f"  JSON: {OUTPUT_JSON}")
    print(f"  HTML: {OUTPUT_HTML}")
    print(f"  クレジット: {OUTPUT_CREDITS}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
