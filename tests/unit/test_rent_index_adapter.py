"""賃料(住宅・土地統計調査の家賃階級加重平均)アダプタの単体テスト.

e-Stat 0004021429(令和5年住宅・土地統計調査)から得られる
都道府県 × 家賃階級 × 借家数 のデータを階級代表値で加重平均し、
平均家賃(円/月)を算出するロジックを検証する.
"""

from __future__ import annotations

import pytest

from app.features.data_pipeline.sources.mlit_rent_index import (
    RENT_CLASS_MIDPOINT,
    MlitRentIndexAdapter,
    _aggregate_weighted_rent,
    _area_to_pref,
)


def test_area_to_pref_accepts_prefecture_level_only() -> None:
    assert _area_to_pref("01000") == "01"
    assert _area_to_pref("13000") == "13"
    assert _area_to_pref("47000") == "47"


def test_area_to_pref_rejects_aggregates_and_municipalities() -> None:
    assert _area_to_pref("00000") is None  # 全国計
    assert _area_to_pref("01100") is None  # 札幌市
    assert _area_to_pref("13A01") is None  # 大都市別
    assert _area_to_pref("99000") is None
    assert _area_to_pref("") is None


def test_class_midpoints_cover_expected_ranges() -> None:
    """階級代表値は 02〜19 の 18 階級をカバーする(00=総数 / 01=0円 / 99=不詳は除外)."""
    assert set(RENT_CLASS_MIDPOINT.keys()) == {f"{i:02d}" for i in range(2, 20)}
    # 中央値の単調増加を確認
    midpoints = [RENT_CLASS_MIDPOINT[f"{i:02d}"] for i in range(2, 20)]
    for prev, nxt in zip(midpoints, midpoints[1:]):
        assert prev < nxt


def test_aggregate_weighted_rent_simple_case() -> None:
    """1 都道府県・2 階級で加重平均が正しく算出される."""
    payload = {
        "GET_STATS_DATA": {
            "STATISTICAL_DATA": {
                "DATA_INF": {
                    "VALUE": [
                        # 東京: 30,000〜40,000円階級(代表値 35,000)に 100 戸
                        {"@area": "13000", "@cat03": "08", "@time": "2023000000", "$": "100"},
                        # 東京: 50,000〜60,000円階級(代表値 55,000)に 200 戸
                        {"@area": "13000", "@cat03": "10", "@time": "2023000000", "$": "200"},
                    ]
                }
            }
        }
    }
    records = list(_aggregate_weighted_rent(payload))
    assert len(records) == 1
    rec = records[0]
    assert rec["prefecture_code"] == "13"
    assert rec["indicator_id"] == "rent_index"
    # (35000*100 + 55000*200) / (100+200) = 48,333.33...
    expected = (35_000 * 100 + 55_000 * 200) / 300
    assert abs(rec["value"] - expected) < 0.01
    assert rec["measured_at"] == "2023-01-01"


def test_aggregate_excludes_totals_unknown_and_zero_rent() -> None:
    """'総数'(00) / '0円'(01) / '不詳'(99) は加重平均から除外."""
    payload = {
        "GET_STATS_DATA": {
            "STATISTICAL_DATA": {
                "DATA_INF": {
                    "VALUE": [
                        {"@area": "13000", "@cat03": "00", "@time": "2023000000", "$": "999"},  # 総数
                        {"@area": "13000", "@cat03": "01", "@time": "2023000000", "$": "50"},   # 0円
                        {"@area": "13000", "@cat03": "08", "@time": "2023000000", "$": "100"},  # 35,000
                        {"@area": "13000", "@cat03": "99", "@time": "2023000000", "$": "30"},   # 不詳
                    ]
                }
            }
        }
    }
    records = list(_aggregate_weighted_rent(payload))
    assert len(records) == 1
    # 35,000 * 100 / 100 = 35,000(他は除外される)
    assert records[0]["value"] == 35_000.0


def test_aggregate_ignores_non_prefecture_areas() -> None:
    """全国/市区町村/大都市別の area は除外する."""
    payload = {
        "GET_STATS_DATA": {
            "STATISTICAL_DATA": {
                "DATA_INF": {
                    "VALUE": [
                        {"@area": "00000", "@cat03": "08", "@time": "2023000000", "$": "10000"},
                        {"@area": "13100", "@cat03": "08", "@time": "2023000000", "$": "500"},
                        {"@area": "13000", "@cat03": "08", "@time": "2023000000", "$": "100"},
                    ]
                }
            }
        }
    }
    records = list(_aggregate_weighted_rent(payload))
    assert len(records) == 1
    assert records[0]["prefecture_code"] == "13"
    assert records[0]["value"] == 35_000.0


def test_aggregate_handles_multiple_prefectures() -> None:
    payload = {
        "GET_STATS_DATA": {
            "STATISTICAL_DATA": {
                "DATA_INF": {
                    "VALUE": [
                        {"@area": "01000", "@cat03": "08", "@time": "2023000000", "$": "1000"},   # 北海道 35k
                        {"@area": "13000", "@cat03": "12", "@time": "2023000000", "$": "1000"},   # 東京 75k
                        {"@area": "47000", "@cat03": "07", "@time": "2023000000", "$": "1000"},   # 沖縄 27.5k
                    ]
                }
            }
        }
    }
    records = list(_aggregate_weighted_rent(payload))
    by_pref = {r["prefecture_code"]: r["value"] for r in records}
    assert by_pref == {"01": 35_000.0, "13": 75_000.0, "47": 27_500.0}


def test_adapter_skips_without_app_id(monkeypatch: pytest.MonkeyPatch) -> None:
    """ESTAT_APP_ID 未設定なら fetch は空(実 API を叩かない)."""
    monkeypatch.delenv("ESTAT_APP_ID", raising=False)
    adapter = MlitRentIndexAdapter(app_id=None)
    adapter.app_id = None
    records = list(adapter.fetch())
    assert records == []
