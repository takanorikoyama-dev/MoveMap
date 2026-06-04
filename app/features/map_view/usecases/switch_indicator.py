"""SF-002 SwitchIndicator — 7指標から1つを選び返す.

参照: outputs/06_system_design/05_画面設計.md (SCR-001 指標切替)
"""

from __future__ import annotations

from typing import Literal

import streamlit as st

IndicatorId = Literal[
    "price_index",
    "land_price",
    "rent_index",
    "birth_count",
    "air_quality",
    "disaster_risk",
    "transport_access",
    "public_safety",
    "net_migration",
]

INDICATOR_LABELS: dict[IndicatorId, str] = {
    "price_index": "物価水準",
    "land_price": "地価",
    "rent_index": "賃料相場",
    "birth_count": "出生数",
    "air_quality": "空気質(AQI)",
    "disaster_risk": "災害リスク",
    "transport_access": "交通アクセス",
    "public_safety": "治安",
    "net_migration": "人口流入",
}

# 各指標のアイコン(絵文字)。ラベルと組み合わせて視認性 UP.
INDICATOR_ICONS: dict[IndicatorId, str] = {
    "price_index": "💰",
    "land_price": "🏘️",
    "rent_index": "🏠",
    "birth_count": "👶",
    "air_quality": "🌬️",
    "disaster_risk": "🌀",
    "transport_access": "🚆",
    "public_safety": "👮",
    "net_migration": "📥",
}


def labeled(indicator_id: IndicatorId) -> str:
    """アイコン + 指標名 を返す(例: '💰 物価指数')."""
    return f"{INDICATOR_ICONS.get(indicator_id, '')} {INDICATOR_LABELS.get(indicator_id, indicator_id)}".strip()

# 各指標の単位(列ヘッダ・ツールチップ用)
INDICATOR_UNITS: dict[IndicatorId, str] = {
    "price_index": "(全国=100)",
    "land_price": "(万円/㎡)",
    "rent_index": "(万円/月)",
    "birth_count": "(万人/年)",
    "air_quality": "(指数)",
    "disaster_risk": "(0-5)",
    "transport_access": "(0-5)",
    "public_safety": "(件/千人)",
    "net_migration": "(率‰)",
}

# 各指標の定義(サイドバーで表示)
INDICATOR_DEFINITIONS: dict[IndicatorId, dict[str, str]] = {
    "price_index": {
        "what": (
            "**消費者物価地域差指数**(全国 = 100)。地域間の物価水準そのものを示す指数。"
            "100 超 = 全国平均より物価が高い、100 未満 = 安い。"
            "東京は約 102 前後、沖縄は約 99 前後で、大都市が高く地方が低い直感的な数値になる。"
        ),
        "interpret": "↓ 低いほど物価が安く生活コストが低い(住みやすい)。",
        "source": "e-Stat『小売物価統計調査(構造編)消費者物価地域差指数』0003441258(年次・10大費目=総合)",
    },
    "land_price": {
        "what": "不動産取引の単価(1㎡あたり)。土地+建物の取引データから算出した県平均。",
        "interpret": "↓ 低いほど土地が安く購入しやすい。地方移住検討の重要指標。",
        "source": "国土交通省『不動産情報ライブラリ』不動産取引価格情報(XIT001、2024年)",
    },
    "rent_index": {
        "what": "民営借家の平均月額家賃。家賃階級×借家数を加重平均して算出。",
        "interpret": "↓ 低いほど月々の家賃が安く生活コストが低い。",
        "source": "e-Stat『令和5年(2023)住宅・土地統計調査』0004021429",
    },
    "birth_count": {
        "what": "年間出生数(人)。将来の地域人口・経済活力の代理指標。",
        "interpret": "↑ 高いほど若年人口が活発で地域の将来性が高い。",
        "source": "e-Stat『人口動態統計 確定数』0003412062(年次・最新確定値)",
    },
    "air_quality": {
        "what": (
            "県庁所在地付近の **AQI(総合大気質指数、0-500)** のリアルタイム値。"
            "PM2.5/PM10/O3/CO/NO2/SO2 の中で最も悪い値で算出される総合指標。"
            "値は観測時点に依存(リアルタイム瞬間値)。"
        ),
        "interpret": "↓ 低いほど空気がきれい(0-50=良好、51-100=普通、100超=注意)。",
        "source": "WAQI(World Air Quality Index)観測ステーション",
    },
    "disaster_risk": {
        "what": "地震・洪水・土砂災害など複数のハザードを統合した安全スコア。",
        "interpret": "↓ 低いほど自然災害のリスクが低く安全。",
        "source": "国土数値情報(国土交通省)ハザードデータをローカル計算",
    },
    "transport_access": {
        "what": "県重心から最寄り空港・新幹線駅・高速ICまでの距離を 0〜5 でスコア化。",
        "interpret": "↑ 高いほど交通の便が良く移動しやすい(都心と地方の行き来が容易)。",
        "source": "国土数値情報(国土交通省)主要交通施設データから計算",
    },
    "public_safety": {
        "what": (
            "刑法犯認知件数 / 人口千人(**千人率**、件/千人)。"
            "県別認知件数を県人口で正規化することで、人口規模の差を取り除いた純粋な治安指標として比較可能。"
            "全国平均は概ね 5〜10 件/千人。"
        ),
        "interpret": "↓ 低いほど人口規模に対する犯罪発生数が少ない(=治安が良い)。",
        "source": "e-Stat 警察庁犯罪統計 0003194949(認知件数)÷ 住民基本台帳人口(2020年国勢調査)",
    },
    "net_migration": {
        "what": (
            "他都道府県との人口移動の **転入超過率**(=転入−転出を人口で正規化、‰)。"
            "プラスは流入超過(人気の県)、マイナスは流出超過。"
        ),
        "interpret": "↑ 高いほど人口が流入している(=移住者から選ばれている)。",
        "source": "e-Stat 住民基本台帳人口移動報告 年報 0003443098",
    },
}


def _render_indicator_definitions() -> None:
    """サイドバーに指標定義の一覧をエクスパンダで表示."""
    with st.sidebar.expander("📖 観点の意味と単位(クリックで展開)", expanded=False):
        for ind_id in INDICATOR_LABELS:
            d = INDICATOR_DEFINITIONS[ind_id]
            unit = INDICATOR_UNITS[ind_id]
            st.markdown(f"**{labeled(ind_id)} {unit}**")
            st.markdown(f"・{d['what']}")
            st.caption(f"{d['interpret']}")
            st.caption(f"出典: {d['source']}")
            st.markdown("---")


def switch_indicator() -> IndicatorId:
    """サイドバーで指標を選ばせ、選択中の indicator_id を返す.

    Returns:
        選択された indicator_id.
    """
    # 表示用ラベル(絵文字付き)と内部 ID の往復辞書
    icon_label_to_id: dict[str, IndicatorId] = {labeled(ind): ind for ind in INDICATOR_LABELS}
    options = list(icon_label_to_id.keys())

    chosen_label = st.sidebar.radio(
        "📊 比べたい観点を選ぶ",
        options=options,
        index=0,
        key="selected_indicator_label",
    )
    chosen_id = icon_label_to_id[chosen_label]

    # 選択中指標の説明をすぐ下に表示(現指標の意味を即座に確認できる)
    d = INDICATOR_DEFINITIONS[chosen_id]
    st.sidebar.info(
        f"**{labeled(chosen_id)} {INDICATOR_UNITS[chosen_id]}**\n\n"
        f"{d['what']}\n\n"
        f"_{d['interpret']}_"
    )

    # 全指標の定義(畳んだエクスパンダ)
    _render_indicator_definitions()

    return chosen_id
