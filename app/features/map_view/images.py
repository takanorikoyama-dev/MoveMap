"""都道府県ヒーロー画像 / ギャラリー画像の読み込みヘルパー.

DEC-016 (mode C 公開) に伴う UI ビジュアル刷新で、Unsplash + Wikimedia から
取得した画像メタデータ(seeds/prefecture_images.json)を UI 層に提供する.

設計:
    - 画像本体はダウンロードせず、CDN 直リンクを参照する(Streamlit Cloud 軽量化)
    - 取得スクリプト: scripts/fetch_prefecture_images.py
    - INV-BIZ-008 対応として撮影者クレジット + ライセンスを併せて返す

ライセンス:
    - Unsplash License: クレジット推奨(本ファイル経由で UI に必ず表示)
    - CC-BY-SA 4.0 (Wikimedia): クレジット必須(同上)
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache

from app.shared.config import PROJECT_ROOT
from app.shared.logger import get_logger

logger = get_logger(__name__)

IMAGES_SEED_PATH = PROJECT_ROOT / "seeds" / "prefecture_images.json"


@dataclass(frozen=True, slots=True)
class ImageRef:
    """画像 1 枚分のメタデータ.

    Attributes:
        url: ヒーロー表示用の高解像度 URL(CDN 直リンク, 1080px 幅程度).
        thumb_url: サムネ用の低解像度 URL.
        source: "unsplash" または "wikimedia".
        photographer: 撮影者名(Unsplash の場合は実名、Wikimedia の場合は集合名).
        photographer_url: 撮影者プロフィール or 出典ページ URL.
        license: ライセンス表記("Unsplash License" or "CC-BY-SA 4.0").
        license_url: ライセンス全文への URL.
        description: 画像の alt テキスト(代替テキスト).
        source_url: Unsplash photo ページ or Wikipedia 記事 URL.
    """

    url: str
    thumb_url: str
    source: str
    photographer: str
    photographer_url: str
    license: str
    license_url: str
    description: str
    source_url: str


@dataclass(frozen=True, slots=True)
class PrefectureImages:
    """1 県分のヒーロー + ギャラリー."""

    code: str
    name_ja: str
    name_en: str
    hero: ImageRef | None
    gallery: tuple[ImageRef, ...]


@lru_cache(maxsize=1)
def _load_payload() -> dict[str, PrefectureImages]:
    """seeds/prefecture_images.json をロードしてキャッシュ.

    Returns:
        {pref_code: PrefectureImages} の辞書. ファイルが無ければ空辞書.
    """
    if not IMAGES_SEED_PATH.exists():
        logger.warning(
            f"prefecture_images.json が見つかりません: {IMAGES_SEED_PATH}. "
            "`python scripts/fetch_prefecture_images.py` を実行してください."
        )
        return {}
    try:
        payload = json.loads(IMAGES_SEED_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        logger.error(f"prefecture_images.json の解析失敗: {e}")
        return {}

    result: dict[str, PrefectureImages] = {}
    for item in payload.get("prefectures", []):
        if not isinstance(item, dict):
            continue
        code = item.get("code", "")
        if not code:
            continue
        result[code] = PrefectureImages(
            code=code,
            name_ja=item.get("name_ja", ""),
            name_en=item.get("name_en", ""),
            hero=_to_image_ref(item.get("hero")),
            gallery=tuple(
                ref for ref in (_to_image_ref(g) for g in item.get("gallery", []) or [])
                if ref is not None
            ),
        )
    return result


def _to_image_ref(d: dict | None) -> ImageRef | None:
    if not d or not isinstance(d, dict) or not d.get("url"):
        return None
    return ImageRef(
        url=str(d.get("url", "")),
        thumb_url=str(d.get("thumb_url") or d.get("url", "")),
        source=str(d.get("source", "")),
        photographer=str(d.get("photographer", "")),
        photographer_url=str(d.get("photographer_url", "")),
        license=str(d.get("license", "")),
        license_url=str(d.get("license_url", "")),
        description=str(d.get("description", "")),
        source_url=str(d.get("source_url", "")),
    )


def get_images_for(prefecture_code: str) -> PrefectureImages | None:
    """1 県の画像情報を返す. 未登録なら None."""
    return _load_payload().get(prefecture_code)


def get_hero(prefecture_code: str) -> ImageRef | None:
    """ヒーロー画像 1 枚を返す. なければ None."""
    images = get_images_for(prefecture_code)
    return images.hero if images else None


def get_thumb(prefecture_code: str) -> ImageRef | None:
    """サムネ用画像を返す(ヒーローの thumb_url を使用)."""
    return get_hero(prefecture_code)


def credit_line(image: ImageRef) -> str:
    """Streamlit caption 用のクレジット文字列を組み立てる.

    例:
        "Photo by [John Doe] on Unsplash"
        "Photo via Wikimedia Commons (CC-BY-SA 4.0)"

    Returns:
        Markdown リンク埋め込みの 1 行文字列.
    """
    if image.source == "unsplash":
        photo_link = (
            f"[{image.photographer}]({image.photographer_url})"
            if image.photographer_url else image.photographer
        )
        return f"Photo by {photo_link} on [Unsplash]({image.source_url})"
    if image.source == "wikimedia":
        return (
            f"Photo via [Wikimedia Commons]({image.source_url}) "
            f"([{image.license}]({image.license_url}))"
        )
    return f"Source: {image.source}"


def all_credits_summary() -> str:
    """全 47 県のクレジットを 1 つの Markdown 文字列にまとめる.

    フッターに表示する用. INV-BIZ-008 への準拠ポイントとして
    seeds/image_credits.md へのリンクを提供する.
    """
    payload = _load_payload()
    if not payload:
        return ""
    n_unsplash = sum(
        1 for p in payload.values() if p.hero and p.hero.source == "unsplash"
    )
    n_wiki = sum(
        1 for p in payload.values() if p.hero and p.hero.source == "wikimedia"
    )
    return (
        f"📷 写真提供: Unsplash {n_unsplash} 県分、Wikimedia Commons {n_wiki} 県分。"
        f" 全クレジットは [seeds/image_credits.md]"
        f"(https://github.com/takanorikoyama-dev/MoveMap/blob/training/seeds/image_credits.md)"
        f" に掲載。"
    )


__all__ = [
    "ImageRef",
    "PrefectureImages",
    "all_credits_summary",
    "credit_line",
    "get_hero",
    "get_images_for",
    "get_thumb",
]
