"""TC-DP-08 / TC-DP-09 UpsertCurrentValues の統合テスト(DuckDB in-memory)."""

from __future__ import annotations

from datetime import date

import duckdb
import pytest

from app.features.data_pipeline.usecases.upsert_current_values import upsert_current_values


def test_upsert_inserts_and_sets_status_active(db: duckdb.DuckDBPyConnection) -> None:
    upsert_current_values(
        db,
        [{"prefecture_code": "13", "indicator_id": "price_index", "value": 105.5, "measured_at": date(2024, 1, 1)}],
    )
    (status, value) = db.execute(
        "SELECT status, value FROM current_values WHERE prefecture_code = '13' AND indicator_id = 'price_index'"
    ).fetchone()
    assert status == "active"
    assert value == 105.5


def test_upsert_overwrites_existing(db: duckdb.DuckDBPyConnection) -> None:
    base = {"prefecture_code": "13", "indicator_id": "price_index", "measured_at": date(2024, 1, 1)}
    upsert_current_values(db, [{**base, "value": 100.0}])
    upsert_current_values(db, [{**base, "value": 110.0}])
    (count, value) = db.execute(
        "SELECT COUNT(*), MAX(value) FROM current_values WHERE prefecture_code = '13' AND indicator_id = 'price_index'"
    ).fetchone()
    assert count == 1
    assert value == 110.0


def test_upsert_rejects_unknown_prefecture_via_fk(db: duckdb.DuckDBPyConnection) -> None:
    """INV-DATA-001: FK 制約で未登録の都道府県を拒否."""
    with pytest.raises(duckdb.Error):
        upsert_current_values(
            db,
            [{"prefecture_code": "99", "indicator_id": "price_index", "value": 1.0, "measured_at": date(2024, 1, 1)}],
        )
