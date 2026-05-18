"""data_status.collect_health の統合テスト."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import duckdb
import pytest

import app.features.map_view.data_status as ds_mod
import app.shared.config as config_mod
import app.shared.db as db_mod
from app.shared.db import initialize_schema


@pytest.fixture()
def isolated(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):  # type: ignore[no-untyped-def]
    db_path = tmp_path / "test.duckdb"
    fake = config_mod.Config(
        db_path=db_path,
        seeds_dir=tmp_path / "seeds",
        log_level="INFO",
        estat_app_id=None,
    )
    monkeypatch.setattr(config_mod, "load_config", lambda: fake)
    monkeypatch.setattr(db_mod, "load_config", lambda: fake)
    monkeypatch.setattr(ds_mod, "load_config", lambda: fake)
    return fake


def _seed_minimal(con: duckdb.DuckDBPyConnection) -> None:
    initialize_schema(con)
    con.execute(
        "INSERT INTO data_sources (id, name, url, license, update_frequency) VALUES ('estat', 'e-Stat', 'https://x', 'MIT', 'monthly')"
    )
    con.execute(
        """INSERT INTO indicators (id, name_ja, name_en, unit, category, is_predictable, source_id)
           VALUES ('price_index', '物価', 'P', 'p', 'must', TRUE, 'estat'),
                  ('air_quality', '空気', 'A', 'ug', 'must', FALSE, 'estat')"""
    )


def test_collect_health_returns_db_missing_when_no_file(isolated) -> None:  # type: ignore[no-untyped-def]
    summary = ds_mod.collect_health()
    assert summary.db_exists is False


def test_collect_health_returns_tables_and_indicators(isolated) -> None:  # type: ignore[no-untyped-def]
    con = duckdb.connect(str(isolated.db_path))
    _seed_minimal(con)
    con.close()

    summary = ds_mod.collect_health()
    assert summary.db_exists is True
    table_names = {t.name for t in summary.tables}
    assert "prefectures" in table_names
    assert "indicators" in table_names

    inds = {i.indicator_id for i in summary.indicators}
    assert inds == {"price_index", "air_quality"}


def test_collect_health_reports_has_current_data(isolated) -> None:  # type: ignore[no-untyped-def]
    con = duckdb.connect(str(isolated.db_path))
    _seed_minimal(con)
    con.execute(
        "INSERT INTO prefectures (code, name_ja, name_en, region, centroid_lat, centroid_lon) VALUES ('13', '東京', 'Tokyo', '関東', 35.0, 139.0)"
    )
    con.execute(
        "INSERT INTO current_values (prefecture_code, indicator_id, value, status) VALUES ('13', 'price_index', 100.0, 'active')"
    )
    con.close()

    summary = ds_mod.collect_health()
    assert summary.has_current_data is True
    pi = next(i for i in summary.indicators if i.indicator_id == "price_index")
    assert pi.current_count == 1


def test_collect_health_reports_latest_batch(isolated) -> None:  # type: ignore[no-untyped-def]
    con = duckdb.connect(str(isolated.db_path))
    _seed_minimal(con)
    con.execute("INSERT INTO batch_jobs (job_type, status, ended_at) VALUES ('monthly_etl', 'success', now())")
    con.close()

    summary = ds_mod.collect_health()
    assert summary.latest_batch is not None
    assert summary.latest_batch.status == "success"


def test_collect_health_counts_recent_errors(isolated) -> None:  # type: ignore[no-untyped-def]
    con = duckdb.connect(str(isolated.db_path))
    _seed_minimal(con)
    con.execute("INSERT INTO audit_logs (event_type, target, occurred_at) VALUES ('batch.failure', 'batch_jobs:1', now())")
    con.execute("INSERT INTO audit_logs (event_type, target, occurred_at) VALUES ('batch.partial', 'batch_jobs:2', now())")
    con.execute("INSERT INTO audit_logs (event_type, target, occurred_at) VALUES ('batch.success', 'batch_jobs:3', now())")
    con.close()

    summary = ds_mod.collect_health()
    # success は除外、failure + partial = 2
    assert summary.error_count_last_7days == 2


def test_collect_health_reports_has_predictions_when_model_exists(isolated) -> None:  # type: ignore[no-untyped-def]
    con = duckdb.connect(str(isolated.db_path))
    _seed_minimal(con)
    con.execute(
        """INSERT INTO prediction_models (indicator_id, model_type, parameters, features_used, training_data_range)
           VALUES ('price_index', 'arima', '{}', '[]', '{}')"""
    )
    con.close()

    summary = ds_mod.collect_health()
    assert summary.has_predictions is True
    pi = next(i for i in summary.indicators if i.indicator_id == "price_index")
    assert pi.has_model is True


def test_prefecture_full_table_uses_single_query(isolated, monkeypatch: pytest.MonkeyPatch) -> None:  # type: ignore[no-untyped-def]
    """リファクタ後: DB 接続が 1 度しか行われない."""
    from app.features.map_view import data_provider as dp

    monkeypatch.setattr(dp, "load_config", lambda: isolated)

    call_count = {"n": 0}
    orig_connect = dp._try_connect_readonly

    def counting() -> duckdb.DuckDBPyConnection | None:  # type: ignore[return-value]
        call_count["n"] += 1
        return orig_connect()

    monkeypatch.setattr(dp, "_try_connect_readonly", counting)

    table = dp.prefecture_full_table("13")
    assert call_count["n"] == 1
    assert "price_index" in table
