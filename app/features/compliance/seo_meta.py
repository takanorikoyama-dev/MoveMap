"""View ごとの SEO metadata 定義 (T1-08 / T1-01 / T1-03 / T4-05).

なぜ view ごとに分ける必要があるか:
    検索エンジンは indexed URL ごとに title / description を見てランキングと
    SERP プレビューを決める. site-wide で同じ meta だと、long-tail クエリ
    (例: "47都道府県 ランキング", "移住適合度診断")にヒットしないし、SNS
    シェア時のプレビューも全部同じになって CTR が落ちる.

施策との対応:
    - T1-08: page_title を view ごとに変える
    - T1-01: meta description を view ごとに最適化
    - T1-03: Twitter Card / OGP の title / description を view ごとに
    - T4-05: canonical URL タグを view ごとに発行

参照:
    - outputs/seo/01_action_list.md
    - DEC-016 (mode C 公開)
"""

from __future__ import annotations

from dataclasses import dataclass

# 本番デプロイ URL (DEC-016 mode C)
BASE_URL = "https://movemap.streamlit.app/"
SITE_NAME = "MoveMap"


@dataclass(frozen=True)
class ViewMetadata:
    """1 つの view が公開する SEO metadata."""

    page_title: str
    """st.set_page_config(page_title=...) に渡す.ブラウザタブと SERP の見出しになる."""

    description: str
    """meta description / og:description / twitter:description に共通で使う一文 (160 文字目安)."""

    canonical_path: str
    """canonical URL の `?view=KEY` 部分.home は空文字 (ルートに正規化)."""

    @property
    def canonical_url(self) -> str:
        """完全な canonical URL."""
        if not self.canonical_path:
            return BASE_URL
        return f"{BASE_URL}{self.canonical_path}"


# View key (app/main.py の _VALID_VIEWS と一致) → metadata
VIEW_METADATA: dict[str, ViewMetadata] = {
    "home": ViewMetadata(
        page_title="地方移住MAP|47都道府県を9指標で比較・診断 - MoveMap",
        description=(
            "全国 47 都道府県を 9 指標(物価・地価・賃料・出生・空気質・災害・交通・治安・人口流入)で比較・診断できる地方移住検討ツール。"
            "ARIMA / Prophet による 3 / 5 / 10 年後の予測付き。個人制作のポートフォリオ作品。"
        ),
        canonical_path="",
    ),
    "map": ViewMetadata(
        page_title="47都道府県マップ|9指標ヒートマップ - MoveMap",
        description=(
            "47 都道府県を 9 指標で塗り分け表示。物価・地価・治安・人口流入など気になる観点で全国を一望し、移住先候補を探せます。"
            "現在値だけでなく 3 / 5 / 10 年後の AI 予測でも切替可能。"
        ),
        canonical_path="?view=map",
    ),
    "ranking": ViewMetadata(
        page_title="47都道府県ランキング|物価・地価・治安など9指標 - MoveMap",
        description=(
            "47 都道府県を 9 指標(物価・地価・賃料・出生・空気質・災害・交通・治安・人口流入)でランキング表示。"
            "現在値に加え 3 / 5 / 10 年後の AI 予測値でも並び替えできる地方移住検討ツール。"
        ),
        canonical_path="?view=ranking",
    ),
    "diagnosis": ViewMetadata(
        page_title="移住適合度診断|あなたに合う都道府県は - MoveMap",
        description=(
            "優先したい要素・避けたい要素を選ぶだけで、9 指標から最適な移住先候補 5 県を提示する適合度診断。"
            "無料・登録不要・公的統計ベース。"
        ),
        canonical_path="?view=diagnosis",
    ),
    "compare": ViewMetadata(
        page_title="2県比較|気になる移住先を9指標で見比べる - MoveMap",
        description=(
            "気になる 2 つの都道府県を 9 指標(物価・地価・賃料・出生・空気質・災害・交通・治安・人口流入)で並べて比較。"
            "違いを一目で確認し、移住先候補を絞り込めます。"
        ),
        canonical_path="?view=compare",
    ),
    "detail": ViewMetadata(
        page_title="都道府県の暮らしを見る|9指標+風景+AI予測 - MoveMap",
        description=(
            "気になる都道府県の暮らしを 9 指標 + 風景写真 + 3 / 5 / 10 年後の AI 予測で深掘り。"
            "データドリブンに移住先を検討できる詳細ビュー。"
        ),
        canonical_path="?view=detail",
    ),
    "model": ViewMetadata(
        page_title="AI予測の根拠を見る|ARIMA・Prophetで3/5/10年後 - MoveMap",
        description=(
            "MoveMap の AI 予測(ARIMA / Prophet)のモデル選択根拠と R² 等の品質指標を可視化。"
            "なぜその予測値になったか、どれくらい信頼できるかを透明に公開します。"
        ),
        canonical_path="?view=model",
    ),
    "terms": ViewMetadata(
        page_title="利用規約 - MoveMap",
        description=(
            "MoveMap(個人制作のポートフォリオ作品)の利用規約。"
            "投資・移住助言ではない旨、データの取扱い、責任の範囲などを記載。"
        ),
        canonical_path="?view=terms",
    ),
    "privacy": ViewMetadata(
        page_title="プライバシーポリシー - MoveMap",
        description=(
            "MoveMap のプライバシーポリシー。"
            "Cookie 同意、Google Analytics による匿名アクセスログ、個人情報の取扱い等を記載。"
        ),
        canonical_path="?view=privacy",
    ),
    "contact": ViewMetadata(
        page_title="お問い合わせ - MoveMap",
        description=(
            "MoveMap のお問い合わせ案内。"
            "個人制作のため原則として個別窓口は設けていません。技術的な不具合・データの誤りは任意で GitHub Issue にて受付。"
        ),
        canonical_path="?view=contact",
    ),
}


def get_metadata(view: str | None) -> ViewMetadata:
    """View 名から metadata を返す. 不明な view は home にフォールバック."""
    if view is None or view not in VIEW_METADATA:
        return VIEW_METADATA["home"]
    return VIEW_METADATA[view]


def _escape_attr(s: str) -> str:
    """最小限の HTML 属性エスケープ. content="..." の中に " が来ても安全に."""
    return s.replace("&", "&amp;").replace('"', "&quot;").replace("<", "&lt;").replace(">", "&gt;")


def build_meta_html(meta: ViewMetadata) -> str:
    """指定 view 用の <meta> + <link rel='canonical'> をまとめて返す.

    呼び出し元は st.markdown(..., unsafe_allow_html=True) で注入する.
    """
    desc = _escape_attr(meta.description)
    title = _escape_attr(meta.page_title)
    url = _escape_attr(meta.canonical_url)
    return (
        f'<meta name="description" content="{desc}">\n'
        f'<meta property="og:title" content="{title}">\n'
        f'<meta property="og:description" content="{desc}">\n'
        f'<meta property="og:url" content="{url}">\n'
        f'<meta name="twitter:title" content="{title}">\n'
        f'<meta name="twitter:description" content="{desc}">\n'
        f'<link rel="canonical" href="{url}">'
    )
