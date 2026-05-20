"""🎯 移住タイプ診断(オンボーディング Usecase).

5 つの質問への回答から 7 指標の重みを算出し、住みやすさスコア上位 3 県を提示する.
診断結果はランキングタブの重みスライダーと連動(session_state 経由).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import streamlit as st

from app.features.map_view.ranking import ALL_INDICATORS, compute_ranking, stars_to_unicode
from app.features.map_view.regions import region_of
from app.features.map_view.usecases.switch_indicator import (
    INDICATOR_ICONS,
    INDICATOR_LABELS,
    IndicatorId,
)

Horizon = Literal["current", "3y", "5y", "10y"]


@dataclass(frozen=True)
class DiagnosisAnswers:
    family: str
    work_style: str
    rent_budget: str
    avoid: tuple[str, ...]
    priorities: tuple[str, ...]


# 質問選択肢
FAMILY_OPTIONS: list[tuple[str, str]] = [
    ("solo", "🧍 単身"),
    ("couple", "💑 夫婦のみ"),
    ("family", "👨‍👩‍👧 子育てファミリー"),
    ("multi_gen", "👴 親と同居 / 二世帯"),
]
WORK_OPTIONS: list[tuple[str, str]] = [
    ("retired", "🌅 リタイア(無職 / 年金)"),
    ("remote", "💻 リモートワーク"),
    ("local_job", "🏢 現地で就職"),
    ("startup", "🚀 起業 / フリーランス"),
]
BUDGET_OPTIONS: list[tuple[str, str]] = [
    ("low", "💴 〜5 万円"),
    ("mid", "💴💴 5〜10 万円"),
    ("high", "💴💴💴 10〜15 万円"),
    ("vip", "💎 15 万円以上 / 持ち家予定"),
]
AVOID_OPTIONS: list[tuple[str, str]] = [
    ("disaster", "🌀 災害リスクが高い地域"),
    ("expensive", "💸 物価・生活費が高い地域"),
    ("medical", "🏥 病院・医療機関が遠い地域"),
    ("transport", "🚉 公共交通が不便な地域"),
]
PRIORITY_OPTIONS: list[tuple[str, str]] = [
    ("clean_air", "🌬️ 空気がきれい"),
    ("future_active", "👶 将来も活気がある(人口・出生数)"),
    ("good_access", "🚆 都心や空港に行きやすい"),
    ("low_cost", "💰 生活コストが安い"),
]


def _compute_weights(answers: DiagnosisAnswers) -> dict[IndicatorId, float]:
    """5 つの回答から 7 指標の重み(0-100)を算出.

    加点方式:
        - 全指標ベース 30
        - 家族構成 / 働き方 / 予算 / 避けたい / 優先項目 ごとに +10〜+40
        - 最後に min(100, weight) でクリップ
    """
    weights: dict[IndicatorId, float] = {ind: 30.0 for ind in ALL_INDICATORS}  # type: ignore[misc]

    # 家族構成
    if answers.family == "family":
        weights["birth_count"] += 30
        weights["disaster_risk"] += 30
        weights["air_quality"] += 25
    elif answers.family == "solo":
        weights["transport_access"] += 30
        weights["price_index"] += 15
    elif answers.family == "couple":
        weights["price_index"] += 25
        weights["rent_index"] += 20
        weights["air_quality"] += 20
    elif answers.family == "multi_gen":
        weights["disaster_risk"] += 30
        weights["transport_access"] += 20

    # 働き方
    if answers.work_style == "retired":
        weights["price_index"] += 25
        weights["rent_index"] += 20
        weights["air_quality"] += 25
        weights["disaster_risk"] += 15
    elif answers.work_style == "remote":
        weights["price_index"] += 25
        weights["rent_index"] += 20
        weights["air_quality"] += 30
        weights["transport_access"] += 10
    elif answers.work_style == "local_job":
        weights["birth_count"] += 30
        weights["transport_access"] += 25
    elif answers.work_style == "startup":
        weights["birth_count"] += 25
        weights["transport_access"] += 25

    # 予算
    if answers.rent_budget == "low":
        weights["rent_index"] += 40
        weights["price_index"] += 30
        weights["land_price"] += 20
    elif answers.rent_budget == "mid":
        weights["rent_index"] += 25
        weights["price_index"] += 15
    elif answers.rent_budget == "high":
        weights["rent_index"] += 10
    # vip: 制約なし

    # 避けたいこと
    if "disaster" in answers.avoid:
        weights["disaster_risk"] += 30
    if "expensive" in answers.avoid:
        weights["price_index"] += 25
        weights["rent_index"] += 15
        weights["land_price"] += 15
    if "medical" in answers.avoid:
        weights["transport_access"] += 25
        weights["birth_count"] += 10  # 医療機関は人口集積と相関
    if "transport" in answers.avoid:
        weights["transport_access"] += 30

    # 優先項目
    if "clean_air" in answers.priorities:
        weights["air_quality"] += 30
    if "future_active" in answers.priorities:
        weights["birth_count"] += 25
    if "good_access" in answers.priorities:
        weights["transport_access"] += 30
    if "low_cost" in answers.priorities:
        weights["price_index"] += 20
        weights["rent_index"] += 20

    # 上限 100、最小は 0
    return {ind: max(0.0, min(100.0, w)) for ind, w in weights.items()}


def _reasoning(answers: DiagnosisAnswers, weights: dict[IndicatorId, float]) -> list[str]:
    """ユーザーの選択に応じた重みの理由を箇条書きで生成."""
    items: list[str] = []
    family_label = dict(FAMILY_OPTIONS).get(answers.family, "")
    work_label = dict(WORK_OPTIONS).get(answers.work_style, "")
    budget_label = dict(BUDGET_OPTIONS).get(answers.rent_budget, "")
    items.append(f"**{family_label}** / **{work_label}** / 家賃予算 **{budget_label}**")
    if answers.avoid:
        avoid_labels = [dict(AVOID_OPTIONS).get(a, "") for a in answers.avoid]
        items.append("避けたい: " + " / ".join(avoid_labels))
    if answers.priorities:
        prio_labels = [dict(PRIORITY_OPTIONS).get(p, "") for p in answers.priorities]
        items.append("重視: " + " / ".join(prio_labels))
    # 上位 3 重み
    top3 = sorted(weights.items(), key=lambda kv: kv[1], reverse=True)[:3]
    items.append(
        "→ あなたが特に重視する観点: "
        + " / ".join(f"{INDICATOR_ICONS.get(ind, '')} {INDICATOR_LABELS[ind]}({int(w)})" for ind, w in top3)
    )
    return items


def _apply_to_ranking_sliders(weights: dict[IndicatorId, float], horizon: Horizon) -> None:
    """ランキングタブの重みスライダーに、診断結果を session_state 経由でセット."""
    for ind in ALL_INDICATORS:
        st.session_state[f"weight_{ind}_{horizon}"] = int(weights[ind])  # type: ignore[index]


def show_diagnosis(horizon: Horizon = "current") -> None:
    """診断画面.

    1) 5 問の質問
    2) 「診断する」で重みを算出 → 上位 3 県を表示 + ランキング連動
    """
    st.subheader("🎯 移住タイプ診断")
    st.caption(
        "5 つの質問にお答えいただくと、あなたに合う **おすすめ 3 県** をご提案します。"
        " 結果は「🏆 ランキング」タブの重みスライダーにも自動反映されます。"
    )

    # 質問 1: 家族構成
    st.markdown("### 1. どなたと住まれますか?")
    family = st.radio(
        "family",
        options=[v for _, v in FAMILY_OPTIONS],
        index=1,
        key="diagnosis_family",
        horizontal=True,
        label_visibility="collapsed",
    )

    # 質問 2: 働き方
    st.markdown("### 2. 移住後の働き方は?")
    work = st.radio(
        "work",
        options=[v for _, v in WORK_OPTIONS],
        index=0,
        key="diagnosis_work",
        horizontal=True,
        label_visibility="collapsed",
    )

    # 質問 3: 家賃予算
    st.markdown("### 3. 月の家賃予算はどれくらい?")
    st.caption("持ち家予定の場合は「15 万円以上」を選択してください。")
    budget = st.radio(
        "budget",
        options=[v for _, v in BUDGET_OPTIONS],
        index=1,
        key="diagnosis_budget",
        horizontal=True,
        label_visibility="collapsed",
    )

    # 質問 4: 避けたい
    st.markdown("### 4. 避けたいことは?(複数選択可)")
    avoid_labels = st.multiselect(
        "avoid",
        options=[v for _, v in AVOID_OPTIONS],
        default=[],
        key="diagnosis_avoid",
        label_visibility="collapsed",
    )

    # 質問 5: 重視
    st.markdown("### 5. 特に重視したいことは?(複数選択可)")
    priority_labels = st.multiselect(
        "priorities",
        options=[v for _, v in PRIORITY_OPTIONS],
        default=[],
        key="diagnosis_priorities",
        label_visibility="collapsed",
    )

    st.markdown("---")

    # 内部 ID に逆引き
    family_id = next(k for k, v in FAMILY_OPTIONS if v == family)
    work_id = next(k for k, v in WORK_OPTIONS if v == work)
    budget_id = next(k for k, v in BUDGET_OPTIONS if v == budget)
    avoid_ids = tuple(next(k for k, v in AVOID_OPTIONS if v == lbl) for lbl in avoid_labels)
    priority_ids = tuple(next(k for k, v in PRIORITY_OPTIONS if v == lbl) for lbl in priority_labels)

    answers = DiagnosisAnswers(
        family=family_id,
        work_style=work_id,
        rent_budget=budget_id,
        avoid=avoid_ids,
        priorities=priority_ids,
    )

    cols = st.columns([1.2, 3])
    with cols[0]:
        diagnose_clicked = st.button("🎯 診断する", type="primary", use_container_width=True)
    with cols[1]:
        st.caption("ボタンを押すと、あなたへの推薦 3 県を計算します。")

    if not diagnose_clicked and "diagnosis_done" not in st.session_state:
        return

    if diagnose_clicked:
        st.session_state["diagnosis_done"] = True

    # 重みを算出 → ランキングタブのスライダーに反映 → 上位 3 県を表示
    weights = _compute_weights(answers)
    _apply_to_ranking_sliders(weights, horizon)

    st.success("✅ 診断が完了しました!ランキングタブの重み付けにも自動反映済みです。")

    # 重み根拠
    st.markdown("### あなたの回答と重み付け")
    for line in _reasoning(answers, weights):
        st.markdown(f"- {line}")

    # 上位 3 県
    st.markdown("### 🏆 あなたへのおすすめ 3 県")
    ranks = compute_ranking(horizon=horizon, weights=weights)
    top3 = [r for r in ranks if r.composite_score is not None][:3]

    if not top3:
        st.warning("条件に合う県を計算できませんでした。重みを見直してください。")
        return

    medal_icons = ["🥇", "🥈", "🥉"]
    rec_cols = st.columns(3)
    for i, r in enumerate(top3):
        with rec_cols[i]:
            with st.container(border=True):
                st.markdown(f"### {medal_icons[i]} {r.prefecture_name}")
                st.caption(f"地方: {region_of(r.prefecture_code)} ｜ コード: {r.prefecture_code}")
                st.metric(
                    label="住みやすさスコア",
                    value=f"{r.composite_score:.1f}" if r.composite_score is not None else "—",
                    delta=stars_to_unicode(r.stars),
                )
                # 上位 3 観点のスコア
                ind_scores = [
                    (ind, r.per_indicator_score[ind])
                    for ind in ALL_INDICATORS
                    if r.per_indicator_score[ind] is not None
                ]
                ind_scores.sort(key=lambda kv: kv[1] or 0, reverse=True)
                st.markdown("**得意な観点(上位3):**")
                for ind, sc in ind_scores[:3]:
                    icon = INDICATOR_ICONS.get(ind, "")  # type: ignore[arg-type]
                    label = INDICATOR_LABELS.get(ind, ind)  # type: ignore[arg-type]
                    st.markdown(f"- {icon} {label}: **{sc:.0f}**")

    st.info(
        "💡 もっと細かく見るには **🏆 ランキング** タブを開いてください。"
        " 診断で算出した重みがスライダーに反映されているので、47 県の総合ランキング全体を見られます。"
        " さらに **⚔️ 2県比較** で気になる 2 県のレーダーチャートで詳細比較も可能です。"
    )


__all__ = ["show_diagnosis"]
