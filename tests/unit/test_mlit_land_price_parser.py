"""MLIT 不動産取引価格情報(XIT001)パーサのユニットテスト.

実 API 検証(2026-05-19)で判明したレスポンス構造に基づく:
    - 必須応答キー: TradePrice / Area / UnitPrice / PricePerUnit / Period
    - 単価は UnitPrice > PricePerUnit > TradePrice/Area の優先順で算出
"""

from __future__ import annotations

import pytest

from app.features.data_pipeline.sources.mlit_land_price import (
    MlitLandPriceAdapter,
    _extract_unit_price,
    _parse_land_price_records,
    _period_to_iso,
)


def test_unit_price_prefers_unit_price_field() -> None:
    item = {"UnitPrice": "120000", "TradePrice": "10000000", "Area": "100"}
    assert _extract_unit_price(item) == 120000.0


def test_unit_price_falls_back_to_price_per_unit() -> None:
    item = {"UnitPrice": "", "PricePerUnit": "95000", "TradePrice": "5000000", "Area": "50"}
    assert _extract_unit_price(item) == 95000.0


def test_unit_price_falls_back_to_trade_price_divided_by_area() -> None:
    item = {"UnitPrice": "", "PricePerUnit": "", "TradePrice": "140000000", "Area": "90"}
    result = _extract_unit_price(item)
    assert result is not None
    assert abs(result - 140000000 / 90) < 1e-6


def test_unit_price_rejects_when_area_missing() -> None:
    item = {"UnitPrice": "", "PricePerUnit": "", "TradePrice": "140000000", "Area": ""}
    assert _extract_unit_price(item) is None


def test_unit_price_handles_comma_separated_numbers() -> None:
    item = {"UnitPrice": "1,200,000"}
    assert _extract_unit_price(item) == 1_200_000.0


def test_period_to_iso_extracts_year() -> None:
    assert _period_to_iso("2024年第1四半期") == "2024-01-01"
    assert _period_to_iso("2023年第4四半期") == "2023-01-01"
    assert _period_to_iso("") is None
    assert _period_to_iso(None) is None  # type: ignore[arg-type]


def test_parse_records_skips_invalid_rows() -> None:
    payload = {
        "status": "OK",
        "data": [
            {"TradePrice": "100000000", "Area": "100", "Period": "2024年第1四半期"},  # 1M/m²
            {"TradePrice": "", "Area": "", "Period": ""},  # skip
            {"UnitPrice": "200000", "Period": "2024年第2四半期"},  # 200k/m²
        ],
    }
    records = list(_parse_land_price_records(payload))
    assert len(records) == 2
    assert records[0]["price_per_sqm"] == 1_000_000.0
    assert records[0]["measured_at"] == "2024-01-01"
    assert records[1]["price_per_sqm"] == 200_000.0


def test_adapter_skips_when_no_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """REINFOLIB_API_KEY 未設定なら fetch は空(INV-EXT-001、実 API は叩かない)."""
    monkeypatch.delenv("REINFOLIB_API_KEY", raising=False)
    adapter = MlitLandPriceAdapter(api_key=None)
    # adapter.api_key が ""/None になれば fetch() の冒頭ガードで return
    adapter.api_key = None  # __init__ で env を読んでしまっていた場合に備えて上書き
    records = list(adapter.fetch())
    assert records == []
