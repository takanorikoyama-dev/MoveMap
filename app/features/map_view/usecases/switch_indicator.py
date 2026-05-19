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
]

INDICATOR_LABELS: dict[IndicatorId, str] = {
    "price_index": "物価指数",
    "land_price": "地価",
    "rent_index": "賃料相場",
    "birth_count": "出生数",
    "air_quality": "空気質(PM2.5)",
    "disaster_risk": "災害リスク",
    "transport_access": "交通アクセス",
}

# 各指標の単位(列ヘッダ・ツールチップ用)
INDICATOR_UNITS: dict[IndicatorId, str] = {
    "price_index": "(2020=100)",
    "land_price": "(万円/㎡)",
    "rent_index": "(万円/月)",
    "birth_count": "(万人/年)",
    "air_quality": "(指数)",
    "disaster_risk": "(0-5)",
    "transport_access": "(0-5)",
}

# 各指標の定義(サイドバーで表示)
INDICATOR_DEFINITIONS: dict[IndicatorId, dict[str, str]] = {
    "price_index": {
        "what": "消費者物価指数(CPI)。100を基準に物価水準を示す。",
        "interpret": "↓ 低いほど物価が安く生活コストが低い(住みやすい)。",
        "source": "e-Stat『2020年基準 消費者物価指数』(県庁所在地ベース・月次)",
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
        "what": "県庁所在地付近のPM2.5/AQI(大気質指数)。リアルタイム測定値。",
        "interpret": "↓ 低いほど空気がきれいで健康面で住みやすい。",
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
}


def _render_indicator_definitions() -> None:
    """サイドバーに指標定義の一覧をエクスパンダで表示."""
    with st.sidebar.expander("📖 指標の定義(クリックで展開)", expanded=False):
        for ind_id, label in INDICATOR_LABELS.items():
            d = INDICATOR_DEFINITIONS[ind_id]
            unit = INDICATOR_UNITS[ind_id]
            st.markdown(f"**{label} {unit}**")
            st.markdown(f"・{d['what']}")
            st.caption(f"{d['interpret']}")
            st.caption(f"出典: {d['source']}")
            st.markdown("---")


def switch_indicator() -> IndicatorId:
    """サイドバーで指標を選ばせ、選択中の indicator_id を返す.

    Returns:
        選択された indicator_id.
    """
    label_to_id: dict[str, IndicatorId] = {label: ind for ind, label in INDICATOR_LABELS.items()}

    chosen_label = st.sidebar.radio(
        "指標選択",
        options=list(INDICATOR_LABELS.values()),
        index=0,
        key="selected_indicator_label",
    )
    chosen_id = label_to_id[chosen_label]

    # 選択中指標の説明をすぐ下に表示(現指標の意味を即座に確認できる)
    d = INDICATOR_DEFINITIONS[chosen_id]
    st.sidebar.info(
        f"**{chosen_label} {INDICATOR_UNITS[chosen_id]}**\n\n"
        f"{d['what']}\n\n"
        f"_{d['interpret']}_"
    )

    # 全指標の定義(畳んだエクスパンダ)
    _render_indicator_definitions()

    return chosen_id
