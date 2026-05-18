"""TC-DP-07 NormalizeData の単体テスト."""

from __future__ import annotations

from datetime import date

from app.features.data_pipeline.usecases.normalize_data import normalize_data


def test_normalize_data_converts_prefecture_code_padding() -> None:
    records = normalize_data(
        "estat",
        [{"prefecture_code": 1, "indicator_id": "price_index", "value": 100.0, "measured_at": "2024-01-01"}],
    )
    assert len(records) == 1
    assert records[0]["prefecture_code"] == "01"


def test_normalize_data_coerces_value_string_to_float() -> None:
    records = normalize_data(
        "estat",
        [{"prefecture_code": "13", "indicator_id": "price_index", "value": "105.5", "measured_at": "2024-01-01"}],
    )
    assert records[0]["value"] == 105.5


def test_normalize_data_parses_measured_at() -> None:
    records = normalize_data(
        "estat",
        [{"prefecture_code": "13", "indicator_id": "price_index", "value": 1.0, "measured_at": "2024-06-15"}],
    )
    assert records[0]["measured_at"] == date(2024, 6, 15)


def test_normalize_data_skips_invalid_prefecture() -> None:
    records = normalize_data(
        "estat",
        [
            {"prefecture_code": "99", "indicator_id": "price_index", "value": 1.0, "measured_at": "2024-01-01"},
            {"prefecture_code": "13", "indicator_id": "price_index", "value": 1.0, "measured_at": "2024-01-01"},
        ],
    )
    assert len(records) == 1
    assert records[0]["prefecture_code"] == "13"


def test_normalize_data_skips_missing_indicator() -> None:
    records = normalize_data(
        "estat",
        [{"prefecture_code": "13", "indicator_id": "", "value": 1.0, "measured_at": "2024-01-01"}],
    )
    assert records == []
