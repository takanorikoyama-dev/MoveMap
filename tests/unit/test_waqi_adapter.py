"""WAQI(World Air Quality Index)アダプタの単体テスト.

経緯: 環境省「そらまめ君」の JSON 配信が廃止された(HTML SPA に変更)ため、
代替として WAQI を採用. source_id は data_sources の互換のため env_soramame のまま.
"""

from __future__ import annotations

from app.features.data_pipeline.sources.env_soramame import (
    SoramameAdapter,
    _parse_waqi_feed,
)


def test_parse_waqi_feed_picks_pm25() -> None:
    """data.iaqi.pm25.v を優先採用."""
    payload = {
        "status": "ok",
        "data": {
            "aqi": 55,
            "iaqi": {"pm25": {"v": 18.5}, "pm10": {"v": 25.0}},
            "time": {"iso": "2026-05-18T09:00:00+09:00"},
        },
    }
    record = _parse_waqi_feed("13", payload)
    assert record is not None
    assert record["indicator_id"] == "air_quality"
    assert record["prefecture_code"] == "13"
    assert record["value"] == 18.5
    assert record["measured_at"] == "2026-05-18"


def test_parse_waqi_feed_falls_back_to_aqi_when_no_pm25() -> None:
    payload = {
        "status": "ok",
        "data": {
            "aqi": 42,
            "iaqi": {"pm10": {"v": 30.0}},
            "time": {"s": "2026-05-18 09:00:00"},
        },
    }
    record = _parse_waqi_feed("01", payload)
    assert record is not None
    assert record["value"] == 42.0
    assert record["measured_at"] == "2026-05-18"


def test_parse_waqi_feed_rejects_non_ok_status() -> None:
    payload = {"status": "error", "data": "Invalid key"}
    assert _parse_waqi_feed("13", payload) is None


def test_parse_waqi_feed_rejects_missing_data() -> None:
    assert _parse_waqi_feed("13", {"status": "ok"}) is None
    assert _parse_waqi_feed("13", {}) is None
    assert _parse_waqi_feed("13", "not a dict") is None  # type: ignore[arg-type]


def test_parse_waqi_feed_rejects_negative_value() -> None:
    """WAQI は観測欠損時 aqi=-1 などを返す場合あり."""
    payload = {"status": "ok", "data": {"aqi": -1, "iaqi": {}, "time": {"iso": "2026-05-18"}}}
    assert _parse_waqi_feed("13", payload) is None


def test_parse_waqi_feed_handles_missing_time() -> None:
    payload = {"status": "ok", "data": {"aqi": 30, "iaqi": {}}}
    record = _parse_waqi_feed("13", payload)
    assert record is not None
    assert record["measured_at"] is None


def test_fetch_skipped_without_token() -> None:
    """WAQI_TOKEN 未設定なら fetch は空(INV-EXT-001)."""
    adapter = SoramameAdapter(token=None)
    records = list(adapter.fetch())
    assert records == []
