"""SF-019 LogBatchOutcome — BatchJob.status 更新 + AuditLog 記録.

参照: outputs/06_system_design/03_状態遷移.md (BatchJob)
不変条件: バッチ実行のすべての帰結は batch_jobs と audit_logs の双方で追跡可能であること.
"""

from __future__ import annotations

import json
from typing import Any

import duckdb

from app.domain.batch import BatchStatus
from app.shared.logger import get_logger

logger = get_logger(__name__)


def log_batch_outcome(
    con: duckdb.DuckDBPyConnection,
    job_id: int,
    status: BatchStatus,
    records_processed: int = 0,
    error_details: str | None = None,
    audit_details: dict[str, Any] | None = None,
) -> None:
    """バッチ実行結果を batch_jobs と audit_logs に記録する.

    Args:
        con: DuckDB 接続.
        job_id: 対象 BatchJob.id.
        status: 終了ステータス('success'/'partial'/'failure').
        records_processed: 処理件数の総計.
        error_details: 失敗時の詳細メッセージ.
        audit_details: 監査ログに残す追加情報(json として保存).
    """
    if status == "running":
        raise ValueError("running は終了ステータスではありません。")

    con.execute(
        """
        UPDATE batch_jobs
        SET status = $1,
            ended_at = now(),
            records_processed = $2,
            error_details = $3
        WHERE id = $4
        """,
        [status, records_processed, error_details, job_id],
    )

    con.execute(
        """
        INSERT INTO audit_logs (event_type, target, actor, details)
        VALUES ($1, $2, 'system', $3)
        """,
        [
            f"batch.{status}",
            f"batch_jobs:{job_id}",
            json.dumps(audit_details or {"records_processed": records_processed, "error_details": error_details}),
        ],
    )
    logger.info(f"log_batch_outcome: job_id={job_id} status={status} records={records_processed}")
