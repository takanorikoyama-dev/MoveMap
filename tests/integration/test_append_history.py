"""TC-DP-10 AppendHistory の統合テスト(append-only 検証)."""

from __future__ import annotations

from datetime import date

import duckdb
import pytest

from app.features.data_pipeline.usecases.append_history import append_history


def test_append_history_inserts_rows(db: duckdb.DuckDBPyConnection) -> None:
    appended = append_history(
        db,
        [
            {"prefecture_code": "13", "indicator_id": "price_index", "value": 100.0, "measured_at": date(2024, 1, 1)},
            {"prefecture_code": "13", "indicator_id": "price_index", "value": 101.0, "measured_at": date(2024, 2, 1)},
        ],
    )
    assert appended == 2
    (count,) = db.execute("SELECT COUNT(*) FROM historical_values").fetchone()
    assert count == 2


def test_append_history_skips_records_without_measured_at(db: duckdb.DuckDBPyConnection) -> None:
    appended = append_history(
        db,
        [
            {"prefecture_code": "13", "indicator_id": "price_index", "value": 100.0, "measured_at": None},
            {"prefecture_code": "13", "indicator_id": "price_index", "value": None, "measured_at": date(2024, 1, 1)},
            {"prefecture_code": "13", "indicator_id": "price_index", "value": 102.0, "measured_at": date(2024, 3, 1)},
        ],
    )
    assert appended == 1


def test_append_history_does_not_overwrite_same_period(db: duckdb.DuckDBPyConnection) -> None:
    """append-only: 同一時点でも複数件挿入できる(履歴の再取得を許容)."""
    base = {"prefecture_code": "13", "indicator_id": "price_index", "measured_at": date(2024, 1, 1)}
    append_history(db, [{**base, "value": 100.0}])
    append_history(db, [{**base, "value": 101.0}])
    rows = db.execute(
        "SELECT value FROM historical_values WHERE prefecture_code = '13' AND indicator_id = 'price_index' ORDER BY id"
    ).fetchall()
    assert [r[0] for r in rows] == [100.0, 101.0]


def test_history_update_rejected_via_protected_connection(db: duckdb.DuckDBPyConnection) -> None:
    """INV-DATA-007(DEC-013 第二段階): HistoryProtectedConnection 経由なら UPDATE/DELETE が弾かれる.

    `db` fixture は生 duckdb 接続のため直接 UPDATE は通るが、
    本テストは production の `connect()` で得る wrapper の動作を保証する.
    """
    from app.shared.db import HistoryProtectedConnection, HistoryProtectionError

    append_history(
        db,
        [{"prefecture_code": "13", "indicator_id": "price_index", "value": 100.0, "measured_at": date(2024, 1, 1)}],
    )
    wrapped = HistoryProtectedConnection(db)
    with pytest.raises(HistoryProtectionError):
        wrapped.execute("UPDATE historical_values SET value = 999.0 WHERE prefecture_code = '13'")
    with pytest.raises(HistoryProtectionError):
        wrapped.execute("DELETE FROM historical_values WHERE prefecture_code = '13'")
    # 値は変わっていない
    (val,) = db.execute("SELECT value FROM historical_values WHERE prefecture_code = '13'").fetchone()
    assert val == 100.0
