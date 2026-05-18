"""seed.py の最低限の smoke 用テスト.

詳細な TC-INV-001..011 は Phase 7 続行時に追加する.
"""

from __future__ import annotations

import pytest

duckdb = pytest.importorskip("duckdb")

from app.shared.db import initialize_schema  # noqa: E402


def test_initialize_schema_creates_tables() -> None:
    con = duckdb.connect(":memory:")
    initialize_schema(con)

    tables = {row[0] for row in con.execute("SHOW TABLES").fetchall()}
    expected = {
        "prefectures",
        "data_sources",
        "indicators",
        "current_values",
        "historical_values",
        "prediction_models",
        "model_evaluations",
        "predicted_values",
        "batch_jobs",
        "audit_logs",
    }
    assert expected.issubset(tables), f"missing: {expected - tables}"


def test_initialize_schema_is_idempotent() -> None:
    con = duckdb.connect(":memory:")
    initialize_schema(con)
    initialize_schema(con)  # 2 回目でも例外が出ない
    (count,) = con.execute("SELECT COUNT(*) FROM prefectures").fetchone()
    assert count == 0
