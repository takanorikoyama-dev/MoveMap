"""TC-DP-15 LogBatchOutcome の統合テスト."""

from __future__ import annotations

import duckdb
import pytest

from app.features.data_pipeline.usecases.log_batch_outcome import log_batch_outcome


def _start_batch(db: duckdb.DuckDBPyConnection) -> int:
    (job_id,) = db.execute(
        "INSERT INTO batch_jobs (job_type, status) VALUES ('monthly_etl', 'running') RETURNING id"
    ).fetchone()
    return int(job_id)


def test_log_batch_outcome_updates_status_to_success(db: duckdb.DuckDBPyConnection) -> None:
    job_id = _start_batch(db)
    log_batch_outcome(db, job_id=job_id, status="success", records_processed=42)

    (status, records, ended_at) = db.execute(
        "SELECT status, records_processed, ended_at FROM batch_jobs WHERE id = $1", [job_id]
    ).fetchone()
    assert status == "success"
    assert records == 42
    assert ended_at is not None


def test_log_batch_outcome_appends_audit_log(db: duckdb.DuckDBPyConnection) -> None:
    job_id = _start_batch(db)
    log_batch_outcome(db, job_id=job_id, status="partial", records_processed=10, error_details="one source failed")

    (count,) = db.execute("SELECT COUNT(*) FROM audit_logs WHERE event_type = 'batch.partial'").fetchone()
    assert count == 1

    (target, actor) = db.execute(
        "SELECT target, actor FROM audit_logs WHERE event_type = 'batch.partial' ORDER BY id DESC LIMIT 1"
    ).fetchone()
    assert target == f"batch_jobs:{job_id}"
    assert actor == "system"


def test_log_batch_outcome_rejects_running_status(db: duckdb.DuckDBPyConnection) -> None:
    job_id = _start_batch(db)
    with pytest.raises(ValueError):
        log_batch_outcome(db, job_id=job_id, status="running")  # type: ignore[arg-type]
