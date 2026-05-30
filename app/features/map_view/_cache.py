"""map_view 描画レイヤ用のキャッシュラッパー.

compute_ranking() / values_for() / latest_model_for() などを `st.cache_data`
で包み、ユーザーの horizon 切替・タブ切替が瞬時に反映されるようにする.

設計方針:
    - キャッシュ TTL = 5 分(月次バッチ更新の影響を考慮しすぎる必要なし)
    - 重み付け辞書は tuple 化してハッシュ可能に
    - dataclass は frozen で hashable + pickle 可能、Streamlit cache に乗る
"""

from __future__ import annotations

from typing import Literal

import streamlit as st

from app.features.map_view.data_provider import (
    ModelInfo,
    ValueWithMeta,
    latest_model_for,
    prefecture_full_table,
    values_for,
    values_for_all_indicators,
)
from app.features.map_view.ranking import PrefectureRank, compute_ranking

Horizon = Literal["current", "3y", "5y", "10y"]


def _weights_to_key(weights: dict[str, float] | None) -> tuple[tuple[str, float], ...] | None:
    """重み付け辞書を hashable な tuple に."""
    if not weights:
        return None
    return tuple(sorted((k, float(v)) for k, v in weights.items()))


@st.cache_data(ttl=300, show_spinner=False)
def cached_compute_ranking(
    horizon: Horizon,
    weights_key: tuple[tuple[str, float], ...] | None,
) -> list[PrefectureRank]:
    """compute_ranking の cache 付きラッパー.

    Args:
        horizon: 'current' / '3y' / '5y' / '10y'.
        weights_key: tuple 化された重み(無ければ None で等加重).
    """
    weights = dict(weights_key) if weights_key else None
    return compute_ranking(horizon=horizon, weights=weights)


def cached_ranking(
    horizon: Horizon = "current",
    weights: dict[str, float] | None = None,
) -> list[PrefectureRank]:
    """呼び出し側で使いやすいヘルパー(重みを内部で tuple 化)."""
    return cached_compute_ranking(horizon, _weights_to_key(weights))


@st.cache_data(ttl=300, show_spinner=False)
def cached_values_for(indicator_id: str, horizon: Horizon) -> ValueWithMeta:
    """values_for の cache 付きラッパー."""
    return values_for(indicator_id, horizon)


@st.cache_data(ttl=300, show_spinner=False)
def cached_values_for_all_indicators(
    indicator_ids: tuple[str, ...], horizon: Horizon
) -> dict[str, dict[str, float | None]]:
    """values_for_all_indicators の cache 付きラッパー(全指標一括取得)."""
    return values_for_all_indicators(indicator_ids, horizon)


@st.cache_data(ttl=300, show_spinner=False)
def cached_prefecture_full_table(prefecture_code: str) -> dict[str, dict[str, float | None]]:
    """prefecture_full_table の cache 付きラッパー."""
    return prefecture_full_table(prefecture_code)


@st.cache_data(ttl=300, show_spinner=False)
def cached_latest_model_for(indicator_id: str) -> ModelInfo:
    """latest_model_for の cache 付きラッパー."""
    return latest_model_for(indicator_id)


__all__ = [
    "cached_compute_ranking",
    "cached_latest_model_for",
    "cached_prefecture_full_table",
    "cached_ranking",
    "cached_values_for",
]
