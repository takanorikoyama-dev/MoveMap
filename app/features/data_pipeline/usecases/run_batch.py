"""SF-010 RunBatch — 月次バッチのオーケストレーション.

参照: outputs/06_system_design/01_シーケンス図.md (F1)
不変条件:
    INV-BIZ-004: バッチ開始時に BatchJob レコード必須.
    INV-EXT-001: 外部 API 失敗時は前回値保持(C-01).
    INV-IDEM-001: 同月内に複数回実行されても結果は同等(upsert + append-only).

ステータス判定:
    - 全 SF が成功 → 'success'
    - 一部 source 失敗 or 一部モデル品質未達 → 'partial'
    - 致命的失敗(DB / 学習プロセス全滅) → 'failure'
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

import duckdb

from app.features.data_pipeline.usecases.append_history import append_history
from app.features.data_pipeline.usecases.apply_fallback import apply_fallback
from app.features.data_pipeline.usecases.evaluate_models import evaluate_models
from app.features.data_pipeline.usecases.fetch_external_data import fetch_external_data
from app.features.data_pipeline.usecases.generate_predictions import generate_predictions
from app.features.data_pipeline.usecases.log_batch_outcome import log_batch_outcome
from app.features.data_pipeline.usecases.normalize_data import normalize_data
from app.features.data_pipeline.usecases.retrain_models import retrain_models
from app.features.data_pipeline.usecases.upsert_current_values import upsert_current_values
from app.shared.db import transaction
from app.shared.logger import get_logger

logger = get_logger(__name__)


@dataclass
class SourceOutcome:
    source_id: str
    success: bool
    records_fetched: int = 0
    records_upserted: int = 0
    records_appended: int = 0
    error: str | None = None


@dataclass
class BatchOutcome:
    job_id: int
    status: str  # 'success'/'partial'/'failure'
    records_processed: int = 0
    error: str | None = None
    sources: list[SourceOutcome] = field(default_factory=list)
    models_trained: int = 0
    models_evaluated: int = 0
    predictions_generated: int = 0
    fallbacks_flagged: int = 0


# DataSource ごとに、どの indicator が紐づくか(seeds/indicators.csv を反映)
SOURCE_IDS: tuple[str, ...] = (
    "estat",
    "mlit_land_price",
    "mlit_rent_index",
    "env_soramame",
    "gsi_hazard",
    "mlit_transport",
)


def run_batch(con: duckdb.DuckDBPyConnection) -> BatchOutcome:
    """月次バッチを起動し、各 SF を順次呼び出す.

    エラー処理は段階的:
        - 個別 source の失敗は記録して継続(partial)
        - DB トランザクション失敗は致命的(failure)

    Args:
        con: DuckDB 接続.

    Returns:
        BatchOutcome.
    """
    # SF-010: BatchJob C (INV-BIZ-004)
    result = con.execute(
        """
        INSERT INTO batch_jobs (job_type, status)
        VALUES ('monthly_etl', 'running')
        RETURNING id
        """
    ).fetchone()
    if result is None:
        outcome = BatchOutcome(job_id=-1, status="failure", error="failed to create batch_jobs row")
        logger.error(outcome.error)
        return outcome
    job_id = int(result[0])
    outcome = BatchOutcome(job_id=job_id, status="running")
    logger.info(f"RunBatch start: job_id={job_id}")

    try:
        # SF-011 〜 SF-014: 各 source を順次フェッチして DB へ
        for source_id in SOURCE_IDS:
            source_outcome = _run_source(con, source_id)
            outcome.sources.append(source_outcome)

        # SF-015 〜 SF-018: 予測パイプライン
        try:
            state = retrain_models(con)
            outcome.models_trained = len(state.model_ids)

            evaluations = evaluate_models(con, state)
            outcome.models_evaluated = len(evaluations)

            outcome.predictions_generated = generate_predictions(con, state)
            outcome.fallbacks_flagged = apply_fallback(con, evaluations)
        except Exception as exc:  # noqa: BLE001
            logger.exception("prediction pipeline failed")
            outcome.error = f"prediction_pipeline: {exc}"

        # SF-019: 終了ステータスを判定して LogBatchOutcome
        outcome.records_processed = sum(s.records_upserted for s in outcome.sources)
        outcome.status = _resolve_status(outcome)

        log_batch_outcome(
            con,
            job_id=job_id,
            status=outcome.status,  # type: ignore[arg-type]
            records_processed=outcome.records_processed,
            error_details=outcome.error,
            audit_details={
                "sources": [asdict(s) for s in outcome.sources],
                "models_trained": outcome.models_trained,
                "models_evaluated": outcome.models_evaluated,
                "predictions_generated": outcome.predictions_generated,
                "fallbacks_flagged": outcome.fallbacks_flagged,
            },
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("RunBatch catastrophic failure")
        outcome.status = "failure"
        outcome.error = f"catastrophic: {exc}"
        try:
            log_batch_outcome(
                con,
                job_id=job_id,
                status="failure",
                records_processed=outcome.records_processed,
                error_details=outcome.error,
            )
        except Exception:  # noqa: BLE001
            logger.exception("LogBatchOutcome itself failed")

    logger.info(f"RunBatch end: job_id={job_id} status={outcome.status}")
    return outcome


def _run_source(con: duckdb.DuckDBPyConnection, source_id: str) -> SourceOutcome:
    """1 source の fetch → normalize → upsert + append を実行する."""
    out = SourceOutcome(source_id=source_id, success=False)

    fetch_result = fetch_external_data(source_id)
    if not fetch_result.success:
        out.error = fetch_result.error
        # INV-EXT-001: 失敗時は前回値保持(何も書かない)
        return out

    out.records_fetched = len(fetch_result.records)
    if not fetch_result.records:
        out.success = True  # 取得 0 件は正常(差分なし)
        return out

    normalized = normalize_data(source_id, fetch_result.records)

    try:
        with transaction(con):
            out.records_upserted = upsert_current_values(con, normalized)
            out.records_appended = append_history(con, normalized)
        out.success = True
    except Exception as exc:  # noqa: BLE001
        logger.exception(f"DB write failed for {source_id}")
        out.error = f"db_write: {exc}"

    return out


def _resolve_status(outcome: BatchOutcome) -> str:
    if outcome.error:
        return "partial"
    failed = [s for s in outcome.sources if not s.success]
    if not failed:
        return "success"
    # 全失敗なら致命的
    if len(failed) == len(outcome.sources):
        return "failure"
    return "partial"


def _aggregate_audit_details(outcome: BatchOutcome) -> dict[str, Any]:
    return {
        "sources": [asdict(s) for s in outcome.sources],
        "models_trained": outcome.models_trained,
        "models_evaluated": outcome.models_evaluated,
        "predictions_generated": outcome.predictions_generated,
        "fallbacks_flagged": outcome.fallbacks_flagged,
    }
