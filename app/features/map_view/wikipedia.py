"""Wikipedia API クライアント(市区町村の代表画像 + 概要文を取得).

無料の MediaWiki Action API を利用. レート制限は実用範囲内.

利用規約:
    Wikipedia/Wikimedia Commons のコンテンツは CC-BY-SA ライセンス.
    出典明記が必須. UI 上で「出典: Wikipedia」と明示する.

参照:
    https://ja.wikipedia.org/w/api.php
    https://www.mediawiki.org/wiki/API:Page_info_in_search_results
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.shared.config import PROJECT_ROOT
from app.shared.http_client import HttpRetryExhausted, get_json
from app.shared.logger import get_logger

logger = get_logger(__name__)

WIKI_API_URL = "https://ja.wikipedia.org/w/api.php"
USER_AGENT = "MoveMap/0.1 (https://github.com/takanorikoyama-dev/MoveMap; takanori.koyama@gree.net)"

MUNICIPALITIES_SEED = PROJECT_ROOT / "seeds" / "municipalities.json"

# 観光・文化・街並み・商店街などの関連セクション名(部分一致でチェック).
SECTION_KEYWORDS: tuple[str, ...] = (
    "観光", "名所", "旧跡", "見どころ",
    "文化", "祭", "イベント", "伝統",
    "街並み", "景観", "建築", "町並",
    "商業", "商店", "ショッピング",
    "産業", "特産品", "名物", "グルメ", "食",
    "公園", "自然",
    "出身", "ゆかり",
)

# 画像ファイル名の除外パターン(地図/旗/紋章は街並みではないので除く).
_IMAGE_EXCLUDE_KEYWORDS: tuple[str, ...] = (
    "Flag_", "Flag of", "Emblem_", "Emblem of", "Coat_of_arms", "Coat of arms",
    "_logo", "Logo_", "_map", "Map_of", "OpenStreetMap", "Locator", "locator",
    ".svg",  # 多くの場合シンボル系
)


@dataclass(frozen=True, slots=True)
class WikiSection:
    """Wikipedia 記事のセクションリンク."""
    name: str  # セクション名(例: "観光", "文化")
    anchor: str  # ページ内アンカー URL(例: "...札幌市#観光")


@dataclass(frozen=True, slots=True)
class WikiInfo:
    """Wikipedia から取得した市区町村情報."""
    title: str
    extract: str  # 冒頭の概要文(プレーンテキスト、500 字)
    image_url: str | None  # 代表画像 URL(400px 幅、無ければ None)
    page_url: str  # Wikipedia ページの URL
    gallery_urls: tuple[str, ...] = ()  # 追加の画像 URL(写真ギャラリー用)
    sections: tuple[WikiSection, ...] = ()  # 観光・文化・街並み等のセクションリンク


@lru_cache(maxsize=1)
def load_municipalities() -> dict[str, list[dict[str, str]]]:
    """seeds/municipalities.json をロードしてキャッシュ.

    Returns:
        {pref_code: [{name, wiki_title}, ...]} の辞書.
    """
    if not MUNICIPALITIES_SEED.exists():
        logger.warning(f"municipalities.json が見つかりません: {MUNICIPALITIES_SEED}")
        return {}
    data = json.loads(MUNICIPALITIES_SEED.read_text(encoding="utf-8"))
    return {k: v for k, v in data.items() if not k.startswith("_")}


def get_municipalities_for(pref_code: str) -> list[dict[str, str]]:
    """指定都道府県コードの市区町村リストを返す."""
    return load_municipalities().get(pref_code, [])


def fetch_wiki_info(
    wiki_title: str,
    image_width: int = 400,
    extract_chars: int = 500,
    gallery_limit: int = 6,
) -> WikiInfo | None:
    """Wikipedia から指定ページの概要・画像・セクションを総合的に取得.

    Args:
        wiki_title: ページタイトル(例: "札幌市", "府中市 (東京都)").
        image_width: 代表画像と追加画像のサムネ幅(px).
        extract_chars: 取得する概要文の文字数上限.
        gallery_limit: 追加で取得する画像数(代表 1 枚に加えて).

    Returns:
        WikiInfo. 失敗時は None.
    """
    if not wiki_title:
        return None

    # 1) extract + pageimages(代表画像) + info + sections + images(全画像リスト)
    try:
        payload = get_json(
            WIKI_API_URL,
            params={
                "action": "query",
                "format": "json",
                "prop": "extracts|pageimages|info|images",
                "exintro": "1",
                "explaintext": "1",
                "exchars": str(extract_chars),
                "pithumbsize": str(image_width),
                "inprop": "url",
                "imlimit": "50",
                "redirects": "1",
                "titles": wiki_title,
            },
            headers={"User-Agent": USER_AGENT},
        )
    except HttpRetryExhausted:
        logger.warning(f"Wikipedia query failed: {wiki_title}")
        return None

    pages = payload.get("query", {}).get("pages") or {}
    if not pages:
        return None
    page = next(iter(pages.values()))
    if not isinstance(page, dict) or "missing" in page:
        return None

    title = str(page.get("title") or wiki_title)
    extract = str(page.get("extract") or "").strip()
    thumb = page.get("thumbnail") or {}
    image_url = thumb.get("source") if isinstance(thumb, dict) else None
    page_url = str(page.get("fullurl") or f"https://ja.wikipedia.org/wiki/{title}")

    # 2) ギャラリー候補(images からフィルタ)
    images = page.get("images") or []
    gallery_urls: list[str] = []
    for img in images:
        if not isinstance(img, dict):
            continue
        fname = str(img.get("title") or "")
        if not fname.startswith("ファイル:") and not fname.startswith("File:"):
            continue
        if _is_excluded_image(fname):
            continue
        # Special:FilePath でリダイレクト URL を構築(API 再呼び出し不要)
        clean_name = fname.split(":", 1)[1] if ":" in fname else fname
        encoded = _url_encode_filename(clean_name)
        url = f"https://commons.wikimedia.org/wiki/Special:FilePath/{encoded}?width={image_width}"
        # 代表画像と被らないように
        if image_url and clean_name.replace("_", " ") in image_url.replace("_", " "):
            continue
        gallery_urls.append(url)
        if len(gallery_urls) >= gallery_limit:
            break

    # 3) セクションリンク(観光・文化・街並み等)
    sections: list[WikiSection] = []
    try:
        sec_payload = get_json(
            WIKI_API_URL,
            params={
                "action": "parse",
                "format": "json",
                "page": wiki_title,
                "prop": "sections",
                "redirects": "1",
            },
            headers={"User-Agent": USER_AGENT},
        )
        for sec in sec_payload.get("parse", {}).get("sections") or []:
            if not isinstance(sec, dict):
                continue
            line = str(sec.get("line") or "")
            anchor = str(sec.get("anchor") or "")
            if not line or not anchor:
                continue
            if any(kw in line for kw in SECTION_KEYWORDS):
                sections.append(
                    WikiSection(name=line, anchor=f"{page_url}#{anchor}")
                )
    except HttpRetryExhausted:
        logger.debug(f"Wikipedia sections fetch failed: {wiki_title}")

    return WikiInfo(
        title=title,
        extract=extract,
        image_url=image_url if isinstance(image_url, str) else None,
        page_url=page_url,
        gallery_urls=tuple(gallery_urls),
        sections=tuple(sections[:8]),  # 上位 8 セクション
    )


def _is_excluded_image(fname: str) -> bool:
    """旗・紋章・地図など街並みでない画像を除外."""
    fname_lower = fname.lower()
    for kw in _IMAGE_EXCLUDE_KEYWORDS:
        if kw.lower() in fname_lower:
            return True
    return False


def _url_encode_filename(name: str) -> str:
    """Wikimedia の Special:FilePath 用にスペースをアンダースコアに."""
    import urllib.parse
    return urllib.parse.quote(name.replace(" ", "_"))


__all__ = [
    "WikiInfo",
    "WikiSection",
    "fetch_wiki_info",
    "get_municipalities_for",
    "load_municipalities",
]
