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


@dataclass(frozen=True, slots=True)
class WikiInfo:
    """Wikipedia から取得した市区町村情報."""
    title: str
    extract: str  # 冒頭の概要文(プレーンテキスト)
    image_url: str | None  # 代表画像 URL(400px 幅、無ければ None)
    page_url: str  # Wikipedia ページの URL


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


def fetch_wiki_info(wiki_title: str, image_width: int = 400) -> WikiInfo | None:
    """Wikipedia から指定ページの 概要 + 画像 + URL を取得.

    Args:
        wiki_title: ページタイトル(例: "札幌市", "府中市 (東京都)").
        image_width: 代表画像のサムネ幅(px).

    Returns:
        WikiInfo. 失敗時は None.
    """
    if not wiki_title:
        return None
    try:
        payload = get_json(
            WIKI_API_URL,
            params={
                "action": "query",
                "format": "json",
                "prop": "extracts|pageimages|info",
                "exintro": "1",
                "explaintext": "1",
                "exchars": "200",
                "pithumbsize": str(image_width),
                "inprop": "url",
                "redirects": "1",
                "titles": wiki_title,
            },
            headers={"User-Agent": USER_AGENT},
        )
    except HttpRetryExhausted:
        logger.warning(f"Wikipedia fetch failed: {wiki_title}")
        return None

    pages = payload.get("query", {}).get("pages") or {}
    if not pages:
        return None
    # pages は {page_id: {...}} の dict. 最初のページを取り出す.
    page = next(iter(pages.values()))
    if not isinstance(page, dict) or "missing" in page:
        return None

    extract = str(page.get("extract") or "").strip()
    thumb = page.get("thumbnail") or {}
    image_url = thumb.get("source") if isinstance(thumb, dict) else None
    page_url = str(page.get("fullurl") or f"https://ja.wikipedia.org/wiki/{wiki_title}")

    return WikiInfo(
        title=str(page.get("title") or wiki_title),
        extract=extract,
        image_url=image_url if isinstance(image_url, str) else None,
        page_url=page_url,
    )


__all__ = [
    "WikiInfo",
    "fetch_wiki_info",
    "get_municipalities_for",
    "load_municipalities",
]
