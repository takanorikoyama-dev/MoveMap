"""TC-DP-06 / e-Stat レスポンス parser の単体テスト."""

from __future__ import annotations

import pytest

from app.features.data_pipeline.sources.estat import (
    EStatAdapter,
    _extract_prefecture_code,
    _time_code_to_iso,
)
from app.shared.http_client import HttpSchemaError


def test_extract_prefecture_code_valid() -> None:
    """都道府県レベルの area_code は先頭 2 桁を採用."""
    assert _extract_prefecture_code("01000") == "01"
    assert _extract_prefecture_code("13000") == "13"
    assert _extract_prefecture_code("47000") == "47"


def test_extract_prefecture_code_accepts_sub_prefecture_levels() -> None:
    """e-Stat には市町村レベル('01100') や県庁所在地ベース('13A01') の area_code もある.
    本実装は **先頭 2 桁が 01-47 ならその県のデータとして採用** する(緩和実装).
    """
    assert _extract_prefecture_code("01100") == "01"  # 札幌市 → 北海道
    assert _extract_prefecture_code("13A01") == "13"  # 東京都区部・県庁所在地ベース
    assert _extract_prefecture_code("27000") == "27"


def test_extract_prefecture_code_rejects_aggregates() -> None:
    assert _extract_prefecture_code("00000") is None  # 全国計
    assert _extract_prefecture_code("99999") is None  # 範囲外
    assert _extract_prefecture_code("") is None
    assert _extract_prefecture_code("abc") is None


def test_time_code_to_iso() -> None:
    assert _time_code_to_iso("2024000000") == "2024-01-01"
    assert _time_code_to_iso("2024010000") == "2024-01-01"
    assert _time_code_to_iso("2024120000") == "2024-12-01"
    assert _time_code_to_iso("invalid") is None
    assert _time_code_to_iso("2024130000") is None  # 月 = 13


def test_parse_stats_data_extracts_records() -> None:
    payload = {
        "GET_STATS_DATA": {
            "STATISTICAL_DATA": {
                "DATA_INF": {
                    "VALUE": [
                        {"@area": "01000", "@time": "2024010000", "$": "105.5"},
                        {"@area": "13000", "@time": "2024010000", "$": "107.2"},
                        {"@area": "00000", "@time": "2024010000", "$": "104.8"},  # 全国計 → skip
                        {"@area": "01100", "@time": "2024010000", "$": "106.0"},  # 北海道扱い(緩和)
                    ]
                }
            }
        }
    }
    records = list(EStatAdapter._parse_stats_data("price_index", payload))
    # 同一 prefecture_code('01') の '01000' と '01100' は最新 time のものだけ採用される.
    # ここでは両方とも @time='2024010000' なので、後に来た '01100' の 106.0 が残る.
    # 結果: '01' (106.0), '13' (107.2) の 2 件.
    by_pref = {r["prefecture_code"]: r for r in records}
    assert set(by_pref.keys()) == {"01", "13"}
    assert by_pref["13"]["value"] == 107.2
    assert by_pref["13"]["measured_at"] == "2024-01-01"


def test_parse_stats_data_picks_latest_time_per_prefecture() -> None:
    """同じ都道府県で複数 time がある場合、最新の time のレコードを採用する."""
    payload = {
        "GET_STATS_DATA": {
            "STATISTICAL_DATA": {
                "DATA_INF": {
                    "VALUE": [
                        {"@area": "13000", "@time": "2022000000", "$": "100.0"},
                        {"@area": "13000", "@time": "2024000000", "$": "110.0"},  # 最新
                        {"@area": "13000", "@time": "2023000000", "$": "105.0"},
                    ]
                }
            }
        }
    }
    records = list(EStatAdapter._parse_stats_data("birth_count", payload))
    assert len(records) == 1
    assert records[0]["prefecture_code"] == "13"
    assert records[0]["value"] == 110.0
    assert records[0]["measured_at"] == "2024-01-01"


def test_parse_stats_data_rejects_bad_schema() -> None:
    with pytest.raises(HttpSchemaError):
        list(EStatAdapter._parse_stats_data("price_index", {"BAD": "structure"}))
