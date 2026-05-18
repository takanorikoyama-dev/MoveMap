"""INV-DATA-007 の DB 層強制(DEC-013): HistoryProtectedConnection の単体テスト."""

from __future__ import annotations

from datetime import date

import duckdb
import pytest

from app.shared.db import (
    HistoryProtectedConnection,
    HistoryProtectionError,
    initialize_schema,
)


@pytest.fixture()
def protected():
    """HistoryProtectedConnection でラップした in-memory DB を返す."""
    raw = duckdb.connect(":memory:")
    initialize_schema(raw)
    raw.execute(
        """
        INSERT INTO data_sources (id, name, url, license, update_frequency)
        VALUES ('estat', 'e-Stat', 'https://x', 'MIT', 'monthly')
        """
    )
    raw.execute(
        """
        INSERT INTO indicators (id, name_ja, name_en, unit, category, is_predictable, source_id)
        VALUES ('price_index', '物価指数', 'PriceIndex', 'point', 'must', TRUE, 'estat')
        """
    )
    raw.execute(
        """
        INSERT INTO prefectures (code, name_ja, name_en, region, centroid_lat, centroid_lon)
        VALUES ('13', '東京都', 'Tokyo', '関東', 35.68, 139.69)
        """
    )
    raw.execute(
        """
        INSERT INTO historical_values (prefecture_code, indicator_id, value, measured_at)
        VALUES ('13', 'price_index', 100.0, $1)
        """,
        [date(2024, 1, 1)],
    )
    wrapped = HistoryProtectedConnection(raw)
    try:
        yield wrapped
    finally:
        raw.close()


def test_insert_into_historical_values_is_allowed(protected: HistoryProtectedConnection) -> None:
    """INSERT は許容(append-only そのものは可)."""
    protected.execute(
        """
        INSERT INTO historical_values (prefecture_code, indicator_id, value, measured_at)
        VALUES ('13', 'price_index', 105.0, $1)
        """,
        [date(2024, 2, 1)],
    )
    (count,) = protected.execute("SELECT COUNT(*) FROM historical_values").fetchone()
    assert count == 2


def test_update_on_historical_values_is_blocked(protected: HistoryProtectedConnection) -> None:
    """INV-DATA-007: UPDATE は例外を起こす."""
    with pytest.raises(HistoryProtectionError):
        protected.execute("UPDATE historical_values SET value = 999.0 WHERE prefecture_code = '13'")


def test_delete_from_historical_values_is_blocked(protected: HistoryProtectedConnection) -> None:
    with pytest.raises(HistoryProtectionError):
        protected.execute("DELETE FROM historical_values WHERE prefecture_code = '13'")


def test_truncate_historical_values_is_blocked(protected: HistoryProtectedConnection) -> None:
    with pytest.raises(HistoryProtectionError):
        protected.execute("TRUNCATE historical_values")


def test_truncate_table_historical_values_is_blocked(protected: HistoryProtectedConnection) -> None:
    with pytest.raises(HistoryProtectionError):
        protected.execute("TRUNCATE TABLE historical_values")


def test_blocking_is_case_insensitive(protected: HistoryProtectedConnection) -> None:
    with pytest.raises(HistoryProtectionError):
        protected.execute("update Historical_Values set value = 1.0")


def test_blocking_handles_extra_whitespace(protected: HistoryProtectedConnection) -> None:
    with pytest.raises(HistoryProtectionError):
        protected.execute("  UPDATE   historical_values   SET value = 1.0")


def test_other_tables_are_not_affected(protected: HistoryProtectedConnection) -> None:
    """他テーブルへの UPDATE/DELETE は通常通り通る."""
    # current_values は UPDATE OK
    protected.execute(
        """
        INSERT INTO current_values (prefecture_code, indicator_id, value, status)
        VALUES ('13', 'price_index', 100.0, 'active')
        """
    )
    protected.execute(
        "UPDATE current_values SET value = 110.0 WHERE prefecture_code = '13'"
    )
    (val,) = protected.execute(
        "SELECT value FROM current_values WHERE prefecture_code = '13'"
    ).fetchone()
    assert val == 110.0

    # batch_jobs の DELETE も OK
    protected.execute("INSERT INTO batch_jobs (job_type, status) VALUES ('test', 'success')")
    protected.execute("DELETE FROM batch_jobs WHERE job_type = 'test'")
    (count,) = protected.execute("SELECT COUNT(*) FROM batch_jobs").fetchone()
    assert count == 0


def test_select_from_historical_values_is_allowed(protected: HistoryProtectedConnection) -> None:
    """READ は当然許容."""
    (count,) = protected.execute("SELECT COUNT(*) FROM historical_values").fetchone()
    assert count == 1


def test_executemany_is_also_protected(protected: HistoryProtectedConnection) -> None:
    """INSERT を executemany で複数行投入は OK、UPDATE は弾く."""
    rows = [("13", "price_index", 110.0, date(2024, 3, 1)),
            ("13", "price_index", 120.0, date(2024, 4, 1))]
    protected.executemany(
        """
        INSERT INTO historical_values (prefecture_code, indicator_id, value, measured_at)
        VALUES ($1, $2, $3, $4)
        """,
        rows,
    )

    with pytest.raises(HistoryProtectionError):
        protected.executemany(
            "UPDATE historical_values SET value = $1 WHERE prefecture_code = $2",
            [(1.0, "13")],
        )


def test_getattr_forwards_to_inner_connection(protected: HistoryProtectedConnection) -> None:
    """fetchone / fetchall などは __getattr__ で内側に委譲."""
    protected.execute("SELECT * FROM prefectures WHERE code = '13'")
    row = protected.fetchone()
    assert row is not None
    assert row[0] == "13"
