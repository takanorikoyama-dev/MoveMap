"""SF-004 ShowPrefectureDetail — 1都道府県の全指標×4時点を詳細表示.

参照: outputs/06_system_design/05_画面設計.md (SCR-002)
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from app.features.map_view.data_provider import prefecture_full_table
from app.features.map_view.usecases.switch_horizon import HORIZON_LABELS
from app.features.map_view.usecases.switch_indicator import INDICATOR_LABELS

PREFECTURE_NAMES: dict[str, str] = {
    "01": "北海道", "02": "青森県", "03": "岩手県", "04": "宮城県", "05": "秋田県",
    "06": "山形県", "07": "福島県", "08": "茨城県", "09": "栃木県", "10": "群馬県",
    "11": "埼玉県", "12": "千葉県", "13": "東京都", "14": "神奈川県", "15": "新潟県",
    "16": "富山県", "17": "石川県", "18": "福井県", "19": "山梨県", "20": "長野県",
    "21": "岐阜県", "22": "静岡県", "23": "愛知県", "24": "三重県", "25": "滋賀県",
    "26": "京都府", "27": "大阪府", "28": "兵庫県", "29": "奈良県", "30": "和歌山県",
    "31": "鳥取県", "32": "島根県", "33": "岡山県", "34": "広島県", "35": "山口県",
    "36": "徳島県", "37": "香川県", "38": "愛媛県", "39": "高知県", "40": "福岡県",
    "41": "佐賀県", "42": "長崎県", "43": "熊本県", "44": "大分県", "45": "宮崎県",
    "46": "鹿児島県", "47": "沖縄県",
}


def show_prefecture_detail(prefecture_code: str) -> None:
    """指定都道府県の詳細パネルを表示する.

    Args:
        prefecture_code: JIS X 0401 都道府県コード.
    """
    name = PREFECTURE_NAMES.get(prefecture_code, prefecture_code)
    st.subheader(f"{name}({prefecture_code})詳細")

    table = prefecture_full_table(prefecture_code)

    rows: list[dict[str, str]] = []
    for indicator_id, indicator_label in INDICATOR_LABELS.items():
        row: dict[str, str] = {"指標": indicator_label}
        per_horizon = table.get(indicator_id, {})
        for horizon, horizon_label in HORIZON_LABELS.items():
            val = per_horizon.get(horizon)  # type: ignore[arg-type]
            row[horizon_label] = "—" if val is None else f"{val:,.2f}"
        rows.append(row)

    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True, hide_index=True)
    st.caption("※ 予測対象外の指標(空気質/災害リスク/交通アクセス)は予測列を「—」表示しています。")
