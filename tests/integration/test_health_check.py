"""scripts/health_check.py CLI の統合テスト."""

from __future__ import annotations

import json
from pathlib import Path

import duckdb
import pytest

import app.features.map_view.data_status as ds_mod
import app.shared.config as config_mod
import app.shared.db as db_mod
import scripts.health_check as hc_mod
from app.features.map_view.data_status import BatchStatus, HealthSummary, TableSummary  # noqa: F401
from app.shared.db import initialize_schema


@pytest.fixture()
def isolated(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):  # type: ignore[no-untyped-def]
    db_path = tmp_path / "test.duckdb"
    fake = config_mod.Config(
        db_path=db_path,
        seeds_dir=tmp_path,
        log_level="INFO",
        estat_app_id=None,
    )
    monkeypatch.setattr(config_mod, "load_config", lambda: fake)
    monkeypatch.setattr(db_mod, "load_config", lambda: fake)
    monkeypatch.setattr(ds_mod, "load_config", lambda: fake)
    return fake


def test_evaluate_status_no_db() -> None:
    summary = HealthSummary(db_exists=False, db_path="/tmp/missing")
    code, label = hc_mod._evaluate_status(summary)
    assert code == 2
    assert "abnormal" in label


def test_evaluate_status_failure_batch() -> None:
    summary = HealthSummary(
        db_exists=True,
        db_path="/tmp/x",
        tables=[TableSummary(name="indicators", row_count=7)],  # type: ignore[attr-defined]
        latest_batch=BatchStatus(job_id=1, status="failure", started_at=None, ended_at=None, records_processed=0, error_details=None),
    )
    code, _ = hc_mod._evaluate_status(summary)
    assert code == 2


def test_evaluate_status_partial_batch() -> None:
    summary = HealthSummary(
        db_exists=True,
        db_path="/tmp/x",
        tables=[TableSummary(name="indicators", row_count=7)],  # type: ignore[attr-defined]
        latest_batch=BatchStatus(job_id=1, status="partial", started_at=None, ended_at=None, records_processed=0, error_details=None),
    )
    code, label = hc_mod._evaluate_status(summary)
    assert code == 1
    assert "warning" in label


def test_evaluate_status_recent_errors() -> None:
    summary = HealthSummary(
        db_exists=True,
        db_path="/tmp/x",
        tables=[TableSummary(name="indicators", row_count=7)],  # type: ignore[attr-defined]
        error_count_last_7days=3,
    )
    code, _ = hc_mod._evaluate_status(summary)
    assert code == 1


def test_evaluate_status_healthy() -> None:
    summary = HealthSummary(
        db_exists=True,
        db_path="/tmp/x",
        tables=[TableSummary(name="indicators", row_count=7)],  # type: ignore[attr-defined]
        latest_batch=BatchStatus(job_id=1, status="success", started_at=None, ended_at=None, records_processed=0, error_details=None),
    )
    code, label = hc_mod._evaluate_status(summary)
    assert code == 0
    assert label == "healthy"


def test_main_returns_2_when_db_missing(isolated, capsys: pytest.CaptureFixture[str]) -> None:  # type: ignore[no-untyped-def]
    rc = hc_mod.main([])
    assert rc == 2
    out = capsys.readouterr().out
    assert "DB" in out


def test_main_json_output(isolated, capsys: pytest.CaptureFixture[str]) -> None:  # type: ignore[no-untyped-def]
    rc = hc_mod.main(["--json"])
    assert rc == 2  # DB missing
    out = capsys.readouterr().out
    parsed = json.loads(out)
    assert parsed["exit_code"] == 2
    assert "summary" in parsed


def test_main_returns_0_when_healthy(isolated, capsys: pytest.CaptureFixture[str]) -> None:  # type: ignore[no-untyped-def]
    con = duckdb.connect(str(isolated.db_path))
    initialize_schema(con)
    con.execute(
        "INSERT INTO data_sources (id, name, url, license, update_frequency) VALUES ('estat', 'e-Stat', 'https://x', 'MIT', 'monthly')"
    )
    con.execute(
        """INSERT INTO indicators (id, name_ja, name_en, unit, category, is_predictable, source_id)
           VALUES ('price_index', '物価', 'P', 'p', 'must', TRUE, 'estat')"""
    )
    con.execute("INSERT INTO batch_jobs (job_type, status, ended_at) VALUES ('monthly_etl', 'success', now())")
    con.close()

    rc = hc_mod.main([])
    assert rc == 0
    out = capsys.readouterr().out
    assert "healthy" in out
