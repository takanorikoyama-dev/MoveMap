"""都道府県画像モジュールの単体テスト.

参照: seeds/prefecture_images.json の構造と images.py の読み込みヘルパー.
INV-BIZ-008: クレジット表示が確実に返されることを検証.
"""

from __future__ import annotations

from app.features.map_view import images as img_mod


def _clear_cache() -> None:
    """`_load_payload` の lru_cache をクリア(JSON 編集後のテスト用)."""
    img_mod._load_payload.cache_clear()


def test_load_returns_47_or_zero_prefectures() -> None:
    """seeds/prefecture_images.json が存在すれば 47 県、無ければ 0 件."""
    _clear_cache()
    payload = img_mod._load_payload()
    assert len(payload) in (0, 47)


def test_get_hero_returns_image_ref_for_existing_pref() -> None:
    """01 北海道のヒーローが取れる(seeds 投入済の場合)."""
    _clear_cache()
    if not img_mod._load_payload():
        return  # seeds 未生成環境ではスキップ
    hero = img_mod.get_hero("01")
    assert hero is not None
    assert hero.url.startswith("https://")
    assert hero.source in ("unsplash", "wikimedia")
    assert hero.license in ("Unsplash License", "CC-BY-SA 4.0")


def test_get_hero_returns_none_for_invalid_code() -> None:
    _clear_cache()
    assert img_mod.get_hero("99") is None


def test_credit_line_for_unsplash_contains_photographer() -> None:
    """Unsplash ソースのクレジット文字列に撮影者リンクが含まれる."""
    ref = img_mod.ImageRef(
        url="https://x", thumb_url="https://x",
        source="unsplash",
        photographer="Jane Doe",
        photographer_url="https://unsplash.com/@janedoe",
        license="Unsplash License",
        license_url="https://unsplash.com/license",
        description="",
        source_url="https://unsplash.com/photos/abc",
    )
    line = img_mod.credit_line(ref)
    assert "Jane Doe" in line
    assert "Unsplash" in line
    assert "https://unsplash.com" in line


def test_credit_line_for_wikimedia_contains_cc_by_sa() -> None:
    ref = img_mod.ImageRef(
        url="https://x", thumb_url="https://x",
        source="wikimedia",
        photographer="Wikimedia Commons contributor",
        photographer_url="https://ja.wikipedia.org/wiki/X",
        license="CC-BY-SA 4.0",
        license_url="https://creativecommons.org/licenses/by-sa/4.0/",
        description="",
        source_url="https://ja.wikipedia.org/wiki/X",
    )
    line = img_mod.credit_line(ref)
    assert "Wikimedia Commons" in line
    assert "CC-BY-SA" in line


def test_all_credits_summary_returns_text_when_seeds_present() -> None:
    """seeds が存在すれば総合クレジット文字列が空でない."""
    _clear_cache()
    if not img_mod._load_payload():
        return
    summary = img_mod.all_credits_summary()
    assert "Unsplash" in summary or "Wikimedia" in summary
