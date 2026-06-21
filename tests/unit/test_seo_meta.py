"""SEO metadata モジュールの単体テスト.

T1-08/01/03/4-05(view ごとの page_title / description / OGP / canonical)を担保.
"""

from __future__ import annotations

import pytest

from app.features.compliance import seo_meta


# ─── ViewMetadata の基本 ───────────────────────────────────────────


def test_all_views_have_metadata() -> None:
    """app/main.py で扱う全 view に metadata が定義されていること."""
    expected = {
        "home",
        "map",
        "ranking",
        "diagnosis",
        "compare",
        "detail",
        "model",
        "terms",
        "privacy",
        "contact",
    }
    assert set(seo_meta.VIEW_METADATA.keys()) == expected


@pytest.mark.parametrize("view_key", list(seo_meta.VIEW_METADATA.keys()))
def test_metadata_fields_nonempty(view_key: str) -> None:
    """各 view の page_title / description が空でないこと(SEO 上致命的)."""
    m = seo_meta.VIEW_METADATA[view_key]
    assert m.page_title.strip(), f"{view_key}: page_title が空"
    assert m.description.strip(), f"{view_key}: description が空"


@pytest.mark.parametrize("view_key", list(seo_meta.VIEW_METADATA.keys()))
def test_page_title_contains_movemap(view_key: str) -> None:
    """page_title にブランド名 MoveMap が含まれる(ブランド統一)."""
    m = seo_meta.VIEW_METADATA[view_key]
    assert "MoveMap" in m.page_title


@pytest.mark.parametrize("view_key", list(seo_meta.VIEW_METADATA.keys()))
def test_description_length_within_seo_budget(view_key: str) -> None:
    """description は SERP プレビューに収まる長さの目安(全角換算 80-160 文字程度)."""
    m = seo_meta.VIEW_METADATA[view_key]
    # 上限のみ守る(80文字未満は短すぎるがエラーにはしない)
    assert len(m.description) <= 220, f"{view_key}: description が長すぎる ({len(m.description)} 文字)"


# ─── canonical URL ────────────────────────────────────────────────


def test_home_canonical_url_is_base() -> None:
    """home の canonical はベース URL そのもの(末尾 /?view=home にしない)."""
    assert seo_meta.VIEW_METADATA["home"].canonical_url == seo_meta.BASE_URL


@pytest.mark.parametrize(
    "view_key",
    ["map", "ranking", "diagnosis", "compare", "detail", "model", "terms", "privacy", "contact"],
)
def test_non_home_canonical_includes_view_query(view_key: str) -> None:
    """home 以外の canonical は `?view=KEY` を含む."""
    m = seo_meta.VIEW_METADATA[view_key]
    assert m.canonical_url == f"{seo_meta.BASE_URL}?view={view_key}"


# ─── フォールバック ────────────────────────────────────────────────


def test_get_metadata_returns_home_for_unknown() -> None:
    """未知の view 名は home にフォールバック."""
    assert seo_meta.get_metadata("nonexistent_view") is seo_meta.VIEW_METADATA["home"]
    assert seo_meta.get_metadata(None) is seo_meta.VIEW_METADATA["home"]
    assert seo_meta.get_metadata("") is seo_meta.VIEW_METADATA["home"]


def test_get_metadata_returns_correct_for_known() -> None:
    """既知の view 名は正しい metadata を返す."""
    assert seo_meta.get_metadata("ranking") is seo_meta.VIEW_METADATA["ranking"]
    assert seo_meta.get_metadata("diagnosis") is seo_meta.VIEW_METADATA["diagnosis"]


# ─── HTML 生成 ─────────────────────────────────────────────────────


@pytest.mark.parametrize("view_key", list(seo_meta.VIEW_METADATA.keys()))
def test_build_meta_html_includes_required_tags(view_key: str) -> None:
    """全 view で必要な meta タグ + canonical link が生成される(T1-01/03/4-05)."""
    m = seo_meta.VIEW_METADATA[view_key]
    html = seo_meta.build_meta_html(m)
    # T1-01
    assert 'name="description"' in html
    # T1-03 OGP
    assert 'property="og:title"' in html
    assert 'property="og:description"' in html
    assert 'property="og:url"' in html
    # T1-03 Twitter Card
    assert 'name="twitter:title"' in html
    assert 'name="twitter:description"' in html
    # T4-05 canonical
    assert 'rel="canonical"' in html


def test_build_meta_html_contains_view_specific_content() -> None:
    """生成 HTML に view 固有の description / canonical が含まれる."""
    m = seo_meta.VIEW_METADATA["ranking"]
    html = seo_meta.build_meta_html(m)
    assert "ランキング" in html
    assert "?view=ranking" in html


def test_build_meta_html_escapes_double_quotes() -> None:
    """description 内のダブルクォートが属性破壊しないことを担保."""
    crafted = seo_meta.ViewMetadata(
        page_title='Test "Title"',
        description='Has "quotes" and <tags>',
        canonical_path="?view=test",
    )
    html = seo_meta.build_meta_html(crafted)
    # 属性破壊しない: 生 " が content 属性の値内に現れない
    assert 'content="Has "quotes" and <tags>"' not in html
    # エスケープ後の表現を含む
    assert "&quot;" in html
    assert "&lt;tags&gt;" in html


# ─── 重複検出 ──────────────────────────────────────────────────────


def test_no_duplicate_page_titles() -> None:
    """全 view で page_title がユニーク(SEO 上、重複は SERP で共食いを起こす)."""
    titles = [m.page_title for m in seo_meta.VIEW_METADATA.values()]
    assert len(titles) == len(set(titles)), "重複した page_title がある"


def test_no_duplicate_canonical_urls() -> None:
    """canonical URL が view ごとにユニーク."""
    urls = [m.canonical_url for m in seo_meta.VIEW_METADATA.values()]
    assert len(urls) == len(set(urls)), "重複した canonical_url がある"
